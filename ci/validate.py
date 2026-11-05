"""Check every skill against the repo convention.

This implements the metadata convention of the skills repo and the rules that
geki-api applies today to `geki-hosts` and `geki-credentials`
(`services/geki-api/app/skills/content.py`, `app/common/guest_env.py`,
`app/env/setup.py` in geki-core). Keep it in line with geki-api: a skill that
passes here must upload without a 400.

Usage: python ci/validate.py [skill ...]
"""

from __future__ import annotations

import ast
import re
import sys
import xml.etree.ElementTree as ET

from common import (
    Skill,
    items,
    load_skills,
    metadata_value,
    skill_slug_ok,
)

ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
HOSTNAME = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$"
)
MAX_REQUIRES = 20
MAX_CREDENTIAL_NAME = 255
TAG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_TAG = 32
MAX_TAGS = 10
MAX_LOGO_BYTES = 64 * 1024

NEVER = {
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "DATABASE_URL",
    "PI_CODING_AGENT_DIR",
    "NODE_OPTIONS",
    "GEKI_SEARCH_URL",
    "GEKI_SEARCH_TIMEOUT_MS",
    "GEKI_KB_URL",
    "PATH",
    "HOME",
    "LD_PRELOAD",
    "LD_LIBRARY_PATH",
    "USER",
    "SHELL",
    "PWD",
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",
    "NODE_EXTRA_CA_CERTS",
    "CURL_CA_BUNDLE",
    "NPM_CONFIG_CACHE",
    "npm_config_cache",
    "UV_CACHE_DIR",
    "WS",
    "CA_BUNDLE",
    "CA_DIR",
    "cmd",
}
RESERVED_PREFIXES = ("OPENAI_", "GEKI_", "PI_", "CODEX_", "GIT_", "AGENT_BROWSER_")
GIT_ALLOWED = {"GIT_TOKEN", "GIT_PASSWORD", "GIT_ACCESS_TOKEN"}

CATEGORIES = {
    "knowledge",
    "tickets",
    "crm",
    "dev",
    "chat",
    "files",
    "finance",
    "hr",
    "marketing",
    "analytics",
    "other",
}
ACCESS = {"read", "write", "read, write"}
AUTH = {"company", "person-oauth", "person-token"}
KNOWN_KEYS = {
    "version",
    "geki-tags",
    "geki-category",
    "geki-access",
    "geki-auth",
    "geki-credentials",
    "geki-settings",
    "geki-hosts",
    "geki-oauth-issuer",
    "geki-oauth-authorize-url",
    "geki-oauth-token-url",
    "geki-oauth-scopes",
    "geki-python",
    "geki-npm",
    "geki-system",
    "geki-image",
    "geki-origin",
}
LICENSES = {"Apache-2.0", "MIT", "BSD-2-Clause", "BSD-3-Clause", "ISC", "CC0-1.0"}
MAX_SKILL_TOKENS = 5000
PACKAGE_IMPORTS = {"pyyaml": "yaml", "beautifulsoup4": "bs4", "pillow": "PIL"}


def reserved(name: str) -> bool:
    if name in NEVER:
        return True
    if name in GIT_ALLOWED:
        return False
    return name.startswith(RESERVED_PREFIXES)


def check_listed(skill: Skill, key: str, errors: list[str]) -> list[str]:
    """Items of a comma-separated key, checked the way geki-api reads them."""
    line_value = metadata_value(skill.lines, key)
    yaml_value = skill.get(key)
    if line_value is not None and line_value != yaml_value:
        errors.append(f"{key}: the line parser of geki-api reads a different value than YAML")
    found = items(line_value)
    if len(list(dict.fromkeys(found))) > MAX_REQUIRES:
        errors.append(f"{key} takes at most {MAX_REQUIRES} entries")
    return found


def check_metadata(skill: Skill, errors: list[str]) -> None:
    meta = skill.meta
    for key, value in meta.items():
        if not isinstance(value, str):
            errors.append(f"metadata.{key} must be a string, quote it")
        if key not in KNOWN_KEYS:
            errors.append(f"metadata.{key} is not in the convention")
    version = skill.get("version")
    if not version.isdigit() or int(version) < 1:
        errors.append("metadata.version must be an integer string of 1 or more")
    tags = check_listed(skill, "geki-tags", errors)
    if not tags:
        errors.append("metadata.geki-tags needs at least one tag")
    if len(tags) > MAX_TAGS:
        errors.append(f"metadata.geki-tags takes at most {MAX_TAGS} tags")
    for tag in tags:
        if len(tag) > MAX_TAG or not TAG.fullmatch(tag):
            errors.append(
                f"geki-tags entry {tag} must be a lowercase slug (a-z, 0-9, single hyphens), at most {MAX_TAG} characters"
            )
    if skill.get("geki-category") not in CATEGORIES:
        errors.append(f"geki-category must be one of {sorted(CATEGORIES)}")
    if skill.get("geki-access") not in ACCESS:
        errors.append("geki-access must be read, write, or read, write")
    auth = skill.list("geki-auth")
    if not auth or not set(auth) <= AUTH:
        errors.append(f"geki-auth must list some of {sorted(AUTH)}")

    credentials = check_listed(skill, "geki-credentials", errors)
    for name in credentials:
        if len(name) > MAX_CREDENTIAL_NAME or not ENV_NAME.fullmatch(name):
            errors.append(f"geki-credentials entry {name} is not an environment variable name")
        elif reserved(name):
            errors.append(f"geki-credentials entry {name} is a reserved name")
    settings = check_listed(skill, "geki-settings", errors)
    for name in settings:
        if not ENV_NAME.fullmatch(name) or reserved(name):
            errors.append(f"geki-settings entry {name} is not a usable variable name")
    if set(credentials) & set(settings):
        errors.append("a variable cannot be both a credential and a setting")
    hosts = check_listed(skill, "geki-hosts", errors)
    for host in hosts:
        if host.startswith("$"):
            if host[1:] not in settings:
                errors.append(f"geki-hosts entry {host} needs {host[1:]} in geki-settings")
        elif not (len(host) <= 253 and HOSTNAME.fullmatch(host)):
            errors.append(f"geki-hosts entry {host} is not a valid host name")
    if credentials and not hosts:
        errors.append("a skill with credentials needs geki-hosts, or they are never injected")
    if ("person-token" in auth or "company" in auth) and not credentials:
        errors.append("geki-auth lists company or person-token but geki-credentials is empty")
    for key in ("geki-oauth-issuer", "geki-oauth-authorize-url", "geki-oauth-token-url"):
        if skill.get(key) and not skill.get(key).startswith("https://"):
            errors.append(f"{key} must be an https URL")
    if skill.get("geki-origin") and not re.fullmatch(r"[a-z0-9-]+@\d+", skill.get("geki-origin")):
        errors.append("geki-origin must look like confluence@3")
    for key in ("geki-python", "geki-npm", "geki-system"):
        check_listed(skill, key, errors)


def check_files(skill: Skill, errors: list[str]) -> None:
    path = skill.path
    for required in ("README.md", "CHANGELOG.md"):
        if not (path / required).exists():
            errors.append(f"{required} is missing")
    scripts = list((path / "scripts").glob("*.py")) + list((path / "scripts").glob("*.mjs"))
    if not scripts:
        errors.append("scripts/ needs a CLI")
    tests = list((path / "tests").glob("test_*.py"))
    tasks = list((path / "tests" / "tasks").glob("*.yaml"))
    if not tests:
        errors.append("tests/ needs script tests (test_*.py)")
    if not tasks:
        errors.append("tests/tasks/ needs agent task files (*.yaml)")
    if skill.list("geki-credentials") and not (path / "references" / "setup.md").exists():
        errors.append("references/setup.md is required when the skill declares credentials")
    tokens = len(skill.text) // 4
    if tokens > MAX_SKILL_TOKENS:
        errors.append(f"SKILL.md is about {tokens} tokens, keep it under {MAX_SKILL_TOKENS}")
    changelog = path / "CHANGELOG.md"
    if changelog.exists():
        heading = re.compile(rf"^## {skill.version}\b", re.MULTILINE)
        if not heading.search(changelog.read_text(encoding="utf-8")):
            errors.append(f"CHANGELOG.md needs a '## {skill.version}' entry")


def stdlib_or_declared(skill: Skill, errors: list[str]) -> None:
    declared = {
        PACKAGE_IMPORTS.get(re.split(r"[<>=!~\[ ]", p, maxsplit=1)[0].lower(), "").lower()
        or re.split(r"[<>=!~\[ ]", p, maxsplit=1)[0].lower().replace("-", "_")
        for p in skill.list("geki-python")
    }
    for script in sorted((skill.path / "scripts").glob("*.py")):
        source = script.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, feature_version=(3, 11))
        except SyntaxError as exc:
            errors.append(f"{script.name}: {exc}")
            continue
        local = {p.stem for p in script.parent.glob("*.py")}
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in sys.stdlib_module_names or name in local:
                    continue
                if name.lower() not in declared:
                    errors.append(
                        f"{script.name} imports {name}, which geki-python does not declare"
                    )
        if re.search(r"pip\s+install|npm\s+install|uv\s+pip", source):
            errors.append(f"{script.name}: no install at run time inside a script")


def check_skill(skill: Skill, errors: list[str]) -> None:
    if skill.yaml_error:
        errors.append(f"frontmatter is not valid YAML: {skill.yaml_error}")
        return
    if not skill.front:
        errors.append("SKILL.md needs a frontmatter")
        return
    if not skill_slug_ok(skill.name) or skill.front.get("name") != skill.name:
        errors.append("name must equal the folder name and be a lowercase slug")
    if not skill.description or "\n" in str(skill.front.get("description", "")).strip():
        errors.append("description must be one non-empty line")
    if len(skill.description) > 1024:
        errors.append("description is longer than 1024 characters")
    if skill.front.get("license") not in LICENSES:
        errors.append(f"license must be one of {sorted(LICENSES)}")
    compat = skill.front.get("compatibility")
    if not isinstance(compat, str) or not compat.strip() or len(compat) > 500:
        errors.append("compatibility must be one short sentence")
    extra = set(skill.front) - {
        "name",
        "description",
        "license",
        "compatibility",
        "metadata",
        "allowed-tools",
    }
    if extra:
        errors.append(f"unexpected frontmatter fields: {sorted(extra)}")
    check_metadata(skill, errors)
    check_files(skill, errors)
    check_logo(skill, errors)
    stdlib_or_declared(skill, errors)


def check_logo(skill: Skill, errors: list[str]) -> None:
    logo = skill.path / "assets" / "logo.svg"
    if not logo.exists():
        return
    if logo.stat().st_size > MAX_LOGO_BYTES:
        errors.append("assets/logo.svg is larger than 64 KB")
    text = logo.read_text(encoding="utf-8")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        errors.append(f"assets/logo.svg is not valid XML: {exc}")
        return
    if not root.tag.endswith("svg"):
        errors.append("assets/logo.svg root is not svg")
    lower = text.lower()
    if (
        "<script" in lower
        or "javascript:" in lower
        or "http://" in lower.replace("http://www.w3.org", "")
    ):
        errors.append("assets/logo.svg has a script or an external reference")


def check_unique_names(skills: list[Skill], errors: dict[str, list[str]]) -> None:
    names = [s.name for s in skills]
    if len(names) != len(set(names)):
        errors.setdefault("repo", []).append("duplicate skill names")


def main(argv: list[str]) -> int:
    everything = load_skills()
    skills = [s for s in everything if not argv or s.name in argv]
    errors: dict[str, list[str]] = {f"skills/{s.name}": [] for s in everything}
    for skill in skills:
        check_skill(skill, errors[f"skills/{skill.name}"])
    if not argv:
        check_unique_names(everything, errors)
    failed = False
    for where, found in errors.items():
        for message in found:
            failed = True
            print(f"{where}: {message}")
    if not failed:
        print(f"ok: {len(skills)} skills")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
