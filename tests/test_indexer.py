from __future__ import annotations

from pathlib import Path

from conftest import make_repo
from mysearcher.indexer import build_index, shortlist, tokenize


def test_tokenize_lowercases_and_splits() -> None:
    assert tokenize("Fix the WidgetParser bug!") == {"fix", "the", "widgetparser", "bug"}


def test_build_index_extracts_python_identifiers(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path,
        {
            "src/widget.py": "class WidgetParser:\n    def parse(self):\n        pass\n",
            "src/other.py": "def unrelated():\n    pass\n",
        },
    )
    index = build_index(repo)
    by_path = {entry.path: entry.identifiers for entry in index}
    assert "WidgetParser" in by_path["src/widget.py"]
    assert "parse" in by_path["src/widget.py"]
    assert by_path["src/other.py"] == ("unrelated",)


def test_shortlist_ranks_matching_file_first(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path,
        {
            "src/widget.py": "class WidgetParser:\n    def parse(self):\n        pass\n",
            "src/other.py": "def unrelated():\n    pass\n",
            "README.md": "nothing relevant here\n",
        },
    )
    result = shortlist(repo, "WidgetParser crashes on empty input", "", top=20)
    assert result[0] == "src/widget.py"


def test_shortlist_falls_back_to_recency_when_nothing_scores(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {"a.py": "x = 1\n", "b.py": "y = 2\n"})
    result = shortlist(repo, "zzz-no-overlap-qqq", "", top=20)
    assert set(result) == {"a.py", "b.py"}
