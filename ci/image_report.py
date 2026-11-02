"""Report the packages that skills declare and the GEKI sandbox image lacks.

    python ci/image_report.py

`ci/geki-image-python.txt` is a copy of `services/geki-api/images/python.in` in
geki-core, the Python libraries of the GEKI sandbox image. Refresh it when that
file changes. Packages that several skills use belong in the image: open a normal
geki-core pull request for them. System and npm packages are listed too: the
image has no way to check them here, so they count as missing.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path

from common import ROOT, load_skills


def normal(name: str) -> str:
    return re.sub(r"[-_.]+", "-", re.split(r"[<>=!~\[ ]", name.strip(), maxsplit=1)[0]).lower()


def main() -> int:
    image = {
        normal(line)
        for line in (ROOT / "ci" / "geki-image-python.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    missing: dict[str, list[str]] = defaultdict(list)
    for skill in load_skills():
        for kind, key in (
            ("python", "geki-python"),
            ("npm", "geki-npm"),
            ("system", "geki-system"),
        ):
            for package in skill.list(key):
                if kind != "python" or normal(package) not in image:
                    missing[f"{kind}: {package}"].append(skill.name)
    lines = ["## Packages that skills need and the GEKI image lacks", ""]
    if not missing:
        lines.append("None. Every skill uses the standard library only, or packages the image has.")
    else:
        lines += ["| Package | Skills | Count |", "| --- | --- | --- |"]
        for package, names in sorted(missing.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            lines.append(f"| `{package}` | {', '.join(names)} | {len(names)} |")
    text = "\n".join(lines)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
