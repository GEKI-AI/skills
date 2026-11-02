"""Helpers shared by the repo checks. Standard library plus PyYAML."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
TOOLS = ROOT / "tools"

REPO_URL = "https://github.com/GEKI-AI/skills"

TEST_ENV = {
    "confluence": lambda url: {
        "CONFLUENCE_URL": url,
        "CONFLUENCE_TOKEN": "tester@example.com:test-token",
    },
    "zammad": lambda url: {"ZAMMAD_URL": url, "ZAMMAD_TOKEN": "test-token"},
    "github": lambda url: {"GITHUB_BASE_URL": url, "GITHUB_TOKEN": "test-token"},
    "hubspot": lambda url: {"HUBSPOT_BASE_URL": url, "HUBSPOT_TOKEN": "test-token"},
}


def split_frontmatter(text: str) -> tuple[list[str], str] | None:
    """Frontmatter lines and body. Same cut rule as geki-api (`content.py`)."""
    if not text.lstrip().startswith("---"):
        return None
    rest = text.lstrip()[3:].lstrip("\n")
    end = rest.find("\n---")
    if end < 0:
        return None
    body = rest[end + 4 :]
    return rest[:end].splitlines(), body.lstrip("\n")


def metadata_value(lines: list[str], key: str) -> str | None:
    """A value under the top-level `metadata:` map. Mirrors `_metadata_value` of geki-api."""
    inside = False
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            name, sep, _rest = line.partition(":")
            inside = bool(sep) and name.strip().lower() == "metadata"
            continue
        if not inside:
            continue
        name, sep, value = line.partition(":")
        if sep and name.strip().strip("\"'").lower() == key:
            return value.split(" #")[0].strip().strip("\"'")
    return None


def items(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class Skill:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.name = path.name
        text = (path / "SKILL.md").read_text(encoding="utf-8")
        self.text = text
        parts = split_frontmatter(text)
        self.lines = parts[0] if parts else []
        self.body = parts[1] if parts else text
        self.front: dict = {}
        self.yaml_error = ""
        if parts:
            try:
                loaded = yaml.safe_load("\n".join(parts[0]))
                self.front = loaded if isinstance(loaded, dict) else {}
            except yaml.YAMLError as exc:
                self.yaml_error = str(exc).splitlines()[0]
        meta = self.front.get("metadata")
        self.meta: dict = meta if isinstance(meta, dict) else {}

    def get(self, key: str) -> str:
        value = self.meta.get(key)
        return value if isinstance(value, str) else ""

    def list(self, key: str) -> list[str]:
        return list(dict.fromkeys(items(self.get(key))))

    @property
    def version(self) -> int:
        try:
            return int(self.get("version"))
        except ValueError:
            return 0

    @property
    def tool(self) -> str:
        return self.get("geki-tool")

    @property
    def description(self) -> str:
        value = self.front.get("description")
        return " ".join(str(value).split()) if value else ""


def skill_paths() -> list[Path]:
    return sorted(p for p in SKILLS.iterdir() if p.is_dir() and (p / "SKILL.md").exists())


def load_skills() -> list[Skill]:
    return [Skill(p) for p in skill_paths()]


def load_tool(tool_id: str) -> dict:
    path = TOOLS / tool_id / "tool.yaml"
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    return loaded if isinstance(loaded, dict) else {}


def run(*cmd: str, cwd: Path = ROOT, check: bool = True) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}: {result.stderr.strip()}")
    return result.stdout


def skill_slug_ok(name: str) -> bool:
    return len(name) <= 64 and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) is not None
