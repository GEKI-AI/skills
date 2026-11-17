import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
SCRIPT = Path(__file__).parents[1] / "scripts" / "report_check.py"

sys.path.insert(0, str(SCRIPT.parent))

import report_check  # noqa: E402


def test_a_clean_report_has_no_problems(cli):
    result = cli(str(FIXTURES / "good.html"), "--no-browser")
    assert result.code == 0, result.err
    assert result.json["problems"] == []
    assert result.json["browser"] is False
    assert (result.json["charts"], result.json["tables"], result.json["lang"]) == (1, 1, "en")
    assert "not measured" in result.json["note"]


def test_the_file_check_names_each_defect(cli):
    problems = cli(str(FIXTURES / "broken.html"), "--no-browser").json["problems"]
    text = "\n".join(problems)
    assert "cdn.example.com/chart.js" in text and "img.example.com/bg.png" in text
    assert "cdn.example.com/report.css" in text
    assert "viewport" in text
    assert "nan hours" in text and "{customer_name}" in text
    assert '1 of 4 shapes in "Tickets per day"' in text
    assert '"Friday afternoon" in "Tickets per day"' in text
    assert len(problems) == 5


def test_text_in_scripts_and_styles_is_not_report_text(cli, tmp_path):
    page = tmp_path / "report.html"
    page.write_text(
        '<meta name="viewport" content="width=device-width"><style>.a{color:red}</style>'
        "<script>const none = null; let x = `${none}`;</script><p>Revenue 12 €</p>",
        encoding="utf-8",
    )
    assert cli(str(page), "--no-browser").json["problems"] == []


def test_shapes_under_a_transform_are_left_alone():
    page = report_check.Page()
    page.feed(
        '<svg viewBox="0 0 100 100"><g transform="translate(0,-500)">'
        '<rect x="10" y="540" width="20" height="30"/></g><circle cx="50" cy="50" r="4"/></svg>'
    )
    assert page.outside == []


def test_a_missing_file_is_an_error(cli):
    result = cli("nothing.html")
    assert result.code == 1
    assert result.error == {"error": "nothing.html is not a file"}


def test_part_needs_a_folder(cli):
    result = cli(str(FIXTURES / "good.html"), "--part", "1280,0,500")
    assert result.code == 1
    assert "needs --shots" in result.error["error"]


CHROME = report_check.find_chrome()


@pytest.mark.skipif(not CHROME, reason="no Chrome on this machine")
def test_a_browser_measures_the_page_and_writes_the_pictures(tmp_path):
    shots = tmp_path / "shots"
    done = subprocess.run(
        [sys.executable, str(SCRIPT), str(FIXTURES / "broken.html"), "--shots", str(shots)],
        capture_output=True,
        text=True,
        check=True,
        timeout=180,
    )
    result = report_check.json.loads(done.stdout)
    text = "\n".join(result["problems"])
    assert "at 390 px: the page scrolls sideways" in text
    assert 'in "Open tickets": <table> is' in text
    assert "1 of 2 shapes are drawn outside the chart area" in text
    assert 'the label "Friday afternoon" runs out of its chart' in text
    assert sorted(p.name for p in shots.iterdir()) == ["page-1280.png", "page-390.png"]
    part = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(FIXTURES / "good.html"),
            "--shots",
            str(shots),
            "--part",
            "390,0,400",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=180,
    )
    assert Path(report_check.json.loads(part.stdout)["image"]).stat().st_size > 2000
