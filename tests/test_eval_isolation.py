"""T12 dev plan 3.3 item 5: the finalised annotation path is read only by the evaluation scripts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_code_never_reads_the_gold():
    for p in (ROOT / "src").rglob("*.py"):
        text = p.read_text()
        assert "annotation/final" not in text and "final_gold" not in text, p
    for p in (ROOT / "skill").rglob("*"):
        if p.is_file() and p.suffix in (".py", ".md", ".json"):
            assert "final_gold" not in p.read_text(), p
