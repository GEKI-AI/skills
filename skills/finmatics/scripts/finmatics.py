#!/usr/bin/env python3
"""Finmatics: upload documents, read and change them, create partners, sum up a month.

Needs FINMATICS_USER and FINMATICS_PASSWORD, sent as HTTP Basic on every request.
The API address comes from FINMATICS_BASE_URL and defaults to
https://api.finmatics.com. Output is JSON on stdout. An error is JSON on stderr
with exit code 1.
"""

from __future__ import annotations

import argparse
import base64
import calendar
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter
from collections.abc import Callable, Iterator
from decimal import Decimal, InvalidOperation
from pathlib import Path

API = "/api/v1"
PAGE_SIZE = 100
AMOUNTS = ("net", "tax", "gross")
SAME_LINE = 0.006


def fail(message: str, status: int | None = None, detail: object = None) -> None:
    print(json.dumps({"error": message, "status": status, "detail": detail}), file=sys.stderr)
    sys.exit(1)


def authorization() -> str:
    user = os.environ.get("FINMATICS_USER", "").strip()
    password = os.environ.get("FINMATICS_PASSWORD", "").strip()
    if not user or not password:
        fail("FINMATICS_USER and FINMATICS_PASSWORD must be set. See references/setup.md.")
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def fetch(
    method: str,
    path: str,
    params: dict | None = None,
    data: bytes | None = None,
    content_type: str | None = None,
    timeout: int = 60,
) -> tuple[bytes, str]:
    base = os.environ.get("FINMATICS_BASE_URL", "").strip() or "https://api.finmatics.com"
    query = urllib.parse.urlencode(params or {})
    url = base.rstrip("/") + API + path + (f"?{query}" if query else "")
    headers = {"Authorization": authorization(), "Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        fail(f"Finmatics answered {exc.code}", exc.code, detail)
    except urllib.error.URLError as exc:
        fail(f"cannot reach Finmatics: {exc.reason}")
    except TimeoutError:
        fail("Finmatics did not answer in time")
    return b"", ""


def call(method: str, path: str, params: dict | None = None, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    content_type = "application/json" if body is not None else None
    raw, _ = fetch(method, path, params, data, content_type)
    return json.loads(raw or b"null")


def doc_path(doc_id: str, suffix: str = "") -> str:
    return f"/documents/{urllib.parse.quote(doc_id, safe='')}/{suffix}"


def amount(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def amounts(doc: dict) -> dict[str, Decimal | None]:
    """Net, tax and gross of a document from `fields=all`.

    This answer leaves totalNetAmount empty until someone changes the document,
    while its lines have the value. The other answers of the API show the same sum.
    """
    net = amount(doc.get("totalNetAmount"))
    if net is None:
        lines = [amount(line.get("netAmount")) for line in doc.get("items") or []]
        known = [value for value in lines if value is not None]
        net = sum(known, Decimal(0)) if known else None
    return {
        "net": net,
        "tax": amount(doc.get("totalTaxAmount")),
        "gross": amount(doc.get("totalGrossAmount")),
    }


def filled(record: dict) -> dict:
    return {k: v for k, v in record.items() if v not in (None, "", [])}


def number(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def summary(doc: dict) -> dict:
    return {
        "id": doc.get("id"),
        "filename": doc.get("filename"),
        "client": doc.get("client"),
        "type": doc.get("bookingName"),
        "status": doc.get("status"),
        "verification_level": doc.get("verificationLevel"),
        "invoice_date": doc.get("invoiceDate"),
        "invoice_no": doc.get("invoiceNo"),
        "partner": doc.get("partnerName") or None,
        "currency": doc.get("currency"),
        **{name: number(value) for name, value in amounts(doc).items()},
    }


def all_pages(path: str, params: dict | None = None) -> Iterator[dict]:
    page = 1
    while True:
        data = call("GET", path, {**(params or {}), "pageSize": PAGE_SIZE, "page": page})
        yield from data.get("results") or []
        if not data.get("next"):
            return
        page += 1


def month_range(month: str) -> tuple[str, str]:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        fail(f"cannot read the month {month!r}: use YYYY-MM")
    year, number = int(month[:4]), int(month[5:])
    return f"{month}-01", f"{month}-{calendar.monthrange(year, number)[1]:02d}"


def find_documents(
    month: str | None, client: str | None, kind: str | None
) -> tuple[dict, Callable[[dict], bool]]:
    """Query parameters and the same conditions as a test on each document.

    Finmatics ignores a filter it does not know without saying so, and a wrong
    month in a sum would not show. So the script applies each condition itself too.
    """
    params: dict = {"fields": "all"}
    if month:
        params["invoiceDate__gte"], params["invoiceDate__lte"] = month_range(month)
    if client:
        params["client"] = client
    if kind:
        params["bookingName"] = kind

    def keep(doc: dict) -> bool:
        if month and not str(doc.get("invoiceDate") or "").startswith(month + "-"):
            return False
        if client and doc.get("client") != client:
            return False
        return not kind or doc.get("bookingName") == kind

    return params, keep


def only_client(given: str | None) -> str:
    """The client to work with: the given one, or the only one of the account."""
    if given:
        return given
    clients = list(all_pages("/clients/"))
    if len(clients) == 1:
        return clients[0]["id"]
    fail(
        "this account has several clients: give one with --client",
        detail=[client_row(c) for c in clients],
    )
    return ""


def client_row(client: dict) -> dict:
    return {
        "id": client.get("id"),
        "name": client.get("clientName"),
        "number": client.get("clientNo"),
    }


def new_totals() -> dict:
    return {"documents": 0, "sums": dict.fromkeys(AMOUNTS, Decimal(0)), "without": Counter()}


def add_up(totals: dict, doc: dict) -> None:
    totals["documents"] += 1
    for name, value in amounts(doc).items():
        if value is None:
            totals["without"][name] += 1
        else:
            totals["sums"][name] += value


def totals_row(key: dict, totals: dict) -> dict:
    def total(name: str) -> float | None:
        empty = totals["without"][name] == totals["documents"]
        return None if empty else float(totals["sums"][name])

    return {
        **key,
        "documents": totals["documents"],
        **{name: total(name) for name in AMOUNTS},
        "documents_without": {name: totals["without"][name] for name in AMOUNTS},
    }


def cmd_clients(_args: argparse.Namespace) -> None:
    print(json.dumps({"results": [client_row(c) for c in all_pages("/clients/")]}))


def cmd_upload(args: argparse.Namespace) -> None:
    path = Path(args.file)
    if not path.is_file():
        fail(f"cannot find the file {args.file!r}")
    client = only_client(args.client)
    boundary = uuid.uuid4().hex
    name = re.sub(r'["\r\n]', "_", path.name)
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        for key, value in (("client", client), ("bookingName", args.type))
    ]
    parts.append(
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode()
        + path.read_bytes()
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    raw, _ = fetch(
        "POST",
        "/documents/",
        data=b"".join(parts),
        content_type=f"multipart/form-data; boundary={boundary}",
        timeout=300,
    )
    print(json.dumps(summary(json.loads(raw))))


def cmd_list(args: argparse.Namespace) -> None:
    params, keep = find_documents(args.month, args.client, args.type)
    params["ordering"] = "-creationDate"
    limit = max(1, args.limit)
    results: list[dict] = []
    more = False
    for doc in all_pages("/documents/", params):
        if not keep(doc):
            continue
        if len(results) == limit:
            more = True
            break
        results.append(summary(doc))
    print(json.dumps({"results": results, "more": more}))


def cmd_get(args: argparse.Namespace) -> None:
    # The default answer has fields such as taxCode, the full one has items. Neither has both.
    default = filled(call("GET", doc_path(args.id)))
    full = filled(call("GET", doc_path(args.id), {"fields": "all"}))
    print(json.dumps({**default, **full}))


def cmd_text(args: argparse.Namespace) -> None:
    pages: dict[int, list[str]] = {}
    current: list[str] = []
    place: tuple | None = None
    for word in call("GET", doc_path(args.id, "text/")).get("results") or []:
        page, top = word.get("page_number"), word["coordinates"]["top"]
        if place and (page != place[0] or abs(top - place[1]) > SAME_LINE):
            pages.setdefault(place[0], []).append(" ".join(current))
            current = []
        current.append(word.get("text") or "")
        place = (page, top)
    if place:
        pages.setdefault(place[0], []).append(" ".join(current))
    rows = [{"page": page, "lines": lines} for page, lines in pages.items()]
    print(json.dumps({"id": args.id, "pages": rows}))


def cmd_download(args: argparse.Namespace) -> None:
    suffix = "original/" if args.original else "pdf/"
    raw, ctype = fetch("GET", doc_path(args.id, suffix), timeout=300)
    Path(args.output).write_bytes(raw)
    print(json.dumps({"id": args.id, "path": args.output, "bytes": len(raw), "type": ctype}))


def parse_sets(pairs: list[str]) -> dict:
    found = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        if not sep or not name.strip():
            fail(f"cannot read {pair!r}: use name=value")
        found[name.strip()] = value
    return found


def cmd_partners(args: argparse.Namespace) -> None:
    # `search` has no effect on this endpoint, so the script compares the names itself.
    name = (args.name or "").casefold()
    limit = max(1, args.limit)
    results: list[dict] = []
    more = False
    for partner in all_pages("/partners/", {"client": args.client} if args.client else None):
        if args.client and partner.get("client") != args.client:
            continue
        if name not in str(partner.get("partnerName") or "").casefold():
            continue
        if args.number and str(partner.get("partnerNo")) != args.number:
            continue
        if len(results) == limit:
            more = True
            break
        results.append(filled(partner))
    print(json.dumps({"results": results, "more": more}))


def cmd_create_partner(args: argparse.Namespace) -> None:
    fields = parse_sets(args.set)
    client = only_client(args.client)
    # A POST with the number of an existing partner overwrites it and answers 201.
    for partner in all_pages("/partners/", {"client": client}):
        same = (
            partner.get("client"),
            str(partner.get("partnerNo")),
            partner.get("bookingCategory"),
        )
        if same == (client, args.number, args.type):
            fail(
                "this partner number exists already, Finmatics would overwrite that partner",
                detail=filled(partner),
            )
    fields.update(
        partnerName=args.name,
        partnerNo=args.number,
        bookingCategory=args.type,
        client=client,
    )
    print(json.dumps(filled(call("POST", "/partners/", body=fields))))


def cmd_update(args: argparse.Namespace) -> None:
    changes = parse_sets(args.set)
    if not changes:
        fail("give at least one --set name=value")
    call("PATCH", doc_path(args.id), body=changes)
    # Finmatics answers 200 also for a field it does not store. Show what it holds now.
    doc = call("GET", doc_path(args.id))
    print(json.dumps({"id": args.id, "stored": {name: doc.get(name) for name in changes}}))


def cmd_stats(args: argparse.Namespace) -> None:
    client = only_client(args.client)
    params, keep = find_documents(args.month, client, args.type)
    totals: dict[tuple, dict] = {}
    partners: dict[tuple, dict] = {}
    levels: Counter = Counter()
    count = 0
    for doc in all_pages("/documents/", params):
        if not keep(doc):
            continue
        count += 1
        levels[str(doc.get("verificationLevel"))] += 1
        kind, currency = doc.get("bookingName"), doc.get("currency")
        add_up(totals.setdefault((kind, currency), new_totals()), doc)
        partner = doc.get("partnerName") or None
        add_up(partners.setdefault((kind, currency, partner), new_totals()), doc)
    by_partner = [
        totals_row({"type": k[0], "currency": k[1], "partner": k[2]}, value)
        for k, value in partners.items()
    ]
    by_partner.sort(key=lambda r: (str(r["type"]), str(r["currency"]), -abs(r["gross"] or 0)))
    print(
        json.dumps(
            {
                "month": args.month,
                "client": client,
                "documents": count,
                "verification_levels": dict(sorted(levels.items())),
                "totals": [
                    totals_row({"type": k[0], "currency": k[1]}, value)
                    for k, value in sorted(totals.items(), key=lambda i: str(i[0]))
                ],
                "by_partner": by_partner,
            }
        )
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Finmatics documents. JSON output.")
    sub = root.add_subparsers(dest="command", required=True)

    def add(name: str, run, help_text: str):
        p = sub.add_parser(name, help=help_text)
        p.set_defaults(run=run)
        return p

    add("clients", cmd_clients, "list the clients of the account")
    p = add("upload", cmd_upload, "upload one file")
    p.add_argument("file")
    p.add_argument("--client", help="client id; needed when the account has several")
    p.add_argument("--type", default="ER", help="booking name, for example ER or AR (default ER)")
    p = add("list", cmd_list, "list documents, newest upload first")
    p.add_argument("--month", help="YYYY-MM, by invoice date")
    p.add_argument("--client", help="client id")
    p.add_argument("--type", help="booking name, for example ER or AR")
    p.add_argument("--limit", type=int, default=25)
    p = add("get", cmd_get, "read all fields of one document")
    p.add_argument("id")
    p = add("text", cmd_text, "read the recognized text of one document")
    p.add_argument("id")
    p = add("download", cmd_download, "save one document as a file")
    p.add_argument("id")
    p.add_argument("--output", required=True, help="path of the file to write")
    p.add_argument("--original", action="store_true", help="the file as uploaded, not the PDF")
    p = add("update", cmd_update, "change fields of one document")
    p.add_argument("id")
    p.add_argument("--set", action="append", default=[], help="name=value, repeat")
    p = add("partners", cmd_partners, "list business partners")
    p.add_argument("--name", help="part of the name, upper or lower case")
    p.add_argument("--number", help="the exact partner number")
    p.add_argument("--client", help="client id")
    p.add_argument("--limit", type=int, default=25)
    p = add("create-partner", cmd_create_partner, "create one business partner")
    p.add_argument("--name", required=True, help="partner name")
    p.add_argument("--number", required=True, help="partner number, at most 20 characters")
    p.add_argument("--type", default="ER", help="booking category, for example ER (default ER)")
    p.add_argument("--client", help="client id; needed when the account has several")
    p.add_argument("--set", action="append", default=[], help="name=value, repeat")
    p = add("stats", cmd_stats, "sums of one month, by invoice date")
    p.add_argument("--month", required=True, help="YYYY-MM")
    p.add_argument("--client", help="client id; needed when the account has several")
    p.add_argument("--type", help="booking name, for example ER or AR")
    return root


def main() -> None:
    args = parser().parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
