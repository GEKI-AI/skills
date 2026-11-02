"""License check for the repo and for adopted code.

    python ci/licenses.py [--installed]

- The root LICENSE is Apache 2.0.
- Every skill names an allowed license in its frontmatter.
- A file with `SPDX-License-Identifier:` names an allowed license.
- A skill that adopts code from elsewhere keeps the original notice in
  `NOTICE` or `THIRD_PARTY.md` (checked when a file says `Adapted from` or `Copyright` of another holder).
- With `--installed`, every package that a skill declares in `geki-python` and that is
  installed has a permissive license (read from its metadata).
"""

from __future__ import annotations

import re
import sys
from importlib import metadata

from common import ROOT, load_skills

ALLOWED = {
    "Apache-2.0",
    "MIT",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "CC0-1.0",
    "Python-2.0",
    "MPL-2.0",
}
PERMISSIVE_WORDS = (
    "apache",
    "mit",
    "bsd",
    "isc",
    "python software foundation",
    "psf",
    "mozilla public",
    "mpl",
)


def main(argv: list[str]) -> int:
    problems: list[str] = []
    root_license = (ROOT / "LICENSE").read_text(encoding="utf-8")
    if "Apache License" not in root_license or "Version 2.0" not in root_license:
        problems.append("LICENSE is not Apache 2.0")
    for skill in load_skills():
        if skill.front.get("license") not in ALLOWED:
            problems.append(f"{skill.name}: license {skill.front.get('license')!r} is not allowed")
        for path in skill.path.rglob("*"):
            if not path.is_file() or path.suffix in {".pyc", ".json", ".svg"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in re.finditer(r"SPDX-License-Identifier:\s*([\w.+-]+)", text):
                if match.group(1) not in ALLOWED:
                    problems.append(
                        f"{path.relative_to(ROOT)}: license {match.group(1)} is not allowed"
                    )
            adopted = re.search(r"Adapted from|Copyright \(c\) \d{4}", text)
            notice = (skill.path / "NOTICE").exists() or (skill.path / "THIRD_PARTY.md").exists()
            if (
                adopted
                and not notice
                and path.name not in {"SKILL.md"}
                and "tests" not in path.parts
            ):
                problems.append(
                    f"{path.relative_to(ROOT)}: adopted code needs a NOTICE or THIRD_PARTY.md"
                )
        if "--installed" in argv:
            for package in skill.list("geki-python"):
                name = re.split(r"[<>=!~\[ ]", package, maxsplit=1)[0]
                try:
                    info = metadata.metadata(name)
                except metadata.PackageNotFoundError:
                    problems.append(f"{skill.name}: {name} is declared but not installed")
                    continue
                text = " ".join(
                    [info.get("License-Expression") or "", info.get("License") or ""]
                    + info.get_all("Classifier", [])
                )
                if not any(word in text.lower() for word in PERMISSIVE_WORDS):
                    problems.append(f"{skill.name}: license of {name} is unclear: {text[:80]!r}")
    for problem in problems:
        print(problem)
    if not problems:
        print("ok: licenses")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
