"""Generate the catalog and the install text from the skill metadata.

Blocks between `<!-- generated:NAME -->` and `<!-- /generated:NAME -->` are
written by this script: in README.md (`catalog`) and in the README.md of every skill (`install`, `variables`, `setup`, `tests`, `tested`).

    python ci/catalog.py                       write the blocks
    python ci/catalog.py --check               fail when a block is out of date
    python ci/catalog.py --results DIR         also write the `tested` blocks of the skills

The `tested` blocks of the skill READMEs come from the test results (`ci/results.py export DIR` copies
them from the branch `test-results`). Without `--results` they stay as they are.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from common import REPO_URL, ROOT, Skill, load_skills, specs_for
from results import load_dir


def first_sentence(text: str) -> str:
    match = re.match(r"(.+?[.!?])(\s|$)", text)
    return match.group(1) if match else text


def ask_pi_sentence(name: str) -> str:
    return (
        f"Install the skill {name} from {REPO_URL} into ~/.agents/skills, "
        "install what its SKILL.md needs, and tell me which environment variables to set."
    )


def packages_line(skill: Skill) -> str:
    lines = []
    if skill.list("geki-python"):
        lines.append("`pip install " + " ".join(skill.list("geki-python")) + "`")
    if skill.list("geki-npm"):
        lines.append("`npm install -g " + " ".join(skill.list("geki-npm")) + "`")
    if skill.list("geki-system"):
        lines.append("system packages: " + ", ".join(f"`{p}`" for p in skill.list("geki-system")))
    if not lines:
        return "The skill needs Python 3.11+ and nothing else. It uses the standard library only."
    return "The skill needs Python 3.11+ and these packages: " + "; ".join(lines) + "."


CATEGORY_TITLES = {
    "knowledge": "Knowledge",
    "tickets": "Tickets",
    "crm": "CRM",
    "dev": "Development",
    "chat": "Chat",
    "files": "Files",
    "finance": "Finance",
    "hr": "HR",
    "marketing": "Marketing",
    "analytics": "Analytics",
    "other": "Other",
}


def catalog_list(skills: list[Skill]) -> str:
    """Skills grouped by category, one short line each."""
    out: list[str] = []
    for category, title in CATEGORY_TITLES.items():
        chosen = sorted(
            (s for s in skills if s.get("geki-category") == category), key=lambda s: s.name
        )
        if not chosen:
            continue
        out.append(f"### {title}\n")
        out += [f"- [`{s.name}`](skills/{s.name}): {first_sentence(s.description)}" for s in chosen]
        out.append("")
    return "\n".join(out).rstrip("\n")


def install_block(skill: Skill) -> str:
    return "\n".join(
        [
            "All skills of the repo as a Pi package (`-l` installs for the current project only):",
            "",
            "```sh\npi install git:github.com/GEKI-AI/skills\n```",
            "",
            "Only this skill. Copy its folder to `~/.agents/skills/` (all projects) or `.agents/skills/` (one project):",
            "",
            f"```sh\ngit clone --depth 1 {REPO_URL}.git /tmp/geki-skills\n"
            f"mkdir -p ~/.agents/skills && cp -r /tmp/geki-skills/skills/{skill.name} ~/.agents/skills/\n```",
            "",
            "Or tell Pi in one sentence:",
            "",
            f"```text\n{ask_pi_sentence(skill.name)}\n```",
            "",
            packages_line(skill),
        ]
    )


def variables_block(skill: Skill) -> str:
    rows = ["| Name | Kind |", "| --- | --- |"]
    for name in skill.list("geki-credentials"):
        rows.append(f"| `{name}` | secret |")
    for name in skill.list("geki-settings"):
        rows.append(f"| `{name}` | setting |")
    if len(rows) == 2:
        return "The skill needs no variables."
    hosts = [
        f"the host of `{h[1:]}`" if h.startswith("$") else f"`{h}`"
        for h in skill.list("geki-hosts")
    ]
    rows.append("")
    if hosts:
        rows.append("Hosts the skill talks to: " + ", ".join(hosts) + ".")
    return "\n".join(rows)


def setup_block(skill: Skill) -> str:
    path = skill.path / "references" / "setup.md"
    if not path.exists():
        return "No setup needed."
    return path.read_text(encoding="utf-8").strip()


def tests_block(skill: Skill) -> str:
    mock = (
        "a Prism mock built from the vendor OpenAPI spec, which also rejects requests that do not match the spec"
        if specs_for(skill.name)
        else "a small mock with fixtures"
    )
    tests = sum(
        len(re.findall(r"^def test_", f.read_text(encoding="utf-8"), re.MULTILINE))
        for f in (skill.path / "tests").glob("test_*.py")
    )
    tasks = len(list((skill.path / "tests" / "tasks").glob("*.yaml")))
    return "\n".join(
        [
            f"- {tests} script tests (pytest) run against {mock}, on Python 3.11 with only the declared packages.",
            f"- {tasks} agent tasks: a vanilla Pi with a model runs each task against the mock, up to three times. A task passes with two passing runs, judged by the requests the mock saw.",
            "- An optional read-only run against a real account can be started by hand. It is not part of the checks.",
        ]
    )


NOT_TESTED = "No test result is recorded yet."


def tested_line(result: dict | None) -> str:
    if not result:
        return NOT_TESTED
    script, agent = result.get("script", {}), result.get("agent", {})
    return (
        f"Last verified on {str(result.get('date', ''))[:10]} with the model {result.get('model')}: "
        f"{script.get('passed', 0)} script tests passed, "
        f"{agent.get('passed', 0)} of {agent.get('tasks', 0)} agent tasks passed."
    )


def replace_block(text: str, name: str, content: str) -> str:
    pattern = re.compile(
        rf"(<!-- generated:{re.escape(name)} -->\n).*?(\n?<!-- /generated:{re.escape(name)} -->)",
        re.DOTALL,
    )
    if not pattern.search(text):
        raise SystemExit(f"missing block generated:{name}")
    return pattern.sub(
        lambda m: f"{m.group(1)}{content}\n{m.group(2).lstrip(chr(10))}", text, count=1
    )


def render(results: dict[str, dict] | None = None) -> dict[Path, str]:
    skills = load_skills()
    out: dict[Path, str] = {}
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = replace_block(text, "catalog", catalog_list(skills))
    out[readme] = text
    for skill in skills:
        path = skill.path / "README.md"
        body = path.read_text(encoding="utf-8")
        for name, fn in (
            ("install", install_block),
            ("variables", variables_block),
            ("setup", setup_block),
            ("tests", tests_block),
        ):
            body = replace_block(body, name, fn(skill))
        if results is not None:
            body = replace_block(body, "tested", tested_line(results.get(skill.name)))
        elif not re.search(r"<!-- generated:tested -->", body):
            raise SystemExit(f"missing block generated:tested in {path}")
        out[path] = body
    return out


def main(argv: list[str]) -> int:
    results = None
    if "--results" in argv:
        results = load_dir(Path(argv[argv.index("--results") + 1]))
    rendered = render(results)
    stale = [p for p, text in rendered.items() if p.read_text(encoding="utf-8") != text]
    if "--check" in argv:
        for path in stale:
            print(f"{path.relative_to(ROOT)} is out of date, run python ci/catalog.py")
        return 1 if stale else 0
    for path in stale:
        path.write_text(rendered[path], encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
