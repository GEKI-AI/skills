"""Generate the catalog and the install text from the skill metadata.

Blocks between `<!-- generated:NAME -->` and `<!-- /generated:NAME -->` are
written by this script: in README.md (`catalog`, `ask-pi`) and in the README.md
of every skill (`install`, `variables`, `setup`, `tests`).

    python ci/catalog.py          write the blocks
    python ci/catalog.py --check  fail when a block is out of date
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from common import REPO_URL, ROOT, Skill, load_skills, load_tool

SIGN_IN = {
    "company": "company token",
    "person-token": "personal token",
    "person-oauth": "personal sign-in",
}


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


def catalog_table(skills: list[Skill]) -> str:
    rows = [
        "| Tool | Skill | What it does | Access | Sign-in |",
        "| --- | --- | --- | --- | --- |",
    ]
    for skill in sorted(
        skills, key=lambda s: (load_tool(s.tool).get("name", s.tool).lower(), s.name)
    ):
        tool = load_tool(skill.tool)
        logo = f"tools/{skill.tool}/logo.svg"
        tool_cell = f'<img src="{logo}" alt="" width="20" height="20"> [{tool.get("name", skill.tool)}]({tool.get("website", "")})'
        sign_in = ", ".join(SIGN_IN.get(a, a) for a in skill.list("geki-auth"))
        rows.append(
            f"| {tool_cell} | [`{skill.name}`](skills/{skill.name}) | {first_sentence(skill.description)} "
            f"| {skill.get('geki-access')} | {sign_in} |"
        )
    return "\n".join(rows)


def ask_pi_block(skills: list[Skill]) -> str:
    out = []
    for skill in skills:
        out.append(f"**{skill.name}**\n\n```text\n{ask_pi_sentence(skill.name)}\n```")
    return "\n\n".join(out)


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
    specs = json.loads((ROOT / "ci" / "specs.json").read_text(encoding="utf-8")).get(skill.tool, [])
    mock = (
        "a Prism mock built from the vendor OpenAPI spec, which also rejects requests that do not match the spec"
        if specs
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
            f"- {tasks} agent tasks: a vanilla Pi with a model runs each task against the mock, three times. A task passes with two of three runs, judged by the requests the mock saw.",
            "- A read-only run against a real account can be started by hand. It finds drift between the real API and the fixtures.",
            "",
            f"[![CI]({REPO_URL}/actions/workflows/ci.yml/badge.svg)]({REPO_URL}/actions/workflows/ci.yml)",
        ]
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


def render() -> dict[Path, str]:
    skills = load_skills()
    out: dict[Path, str] = {}
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = replace_block(text, "catalog", catalog_table(skills))
    text = replace_block(text, "ask-pi", ask_pi_block(skills))
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
        out[path] = body
    return out


def main(argv: list[str]) -> int:
    rendered = render()
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
