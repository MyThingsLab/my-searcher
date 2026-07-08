from __future__ import annotations

import pytest

from mysearcher import cli
from mysearcher.searcher import Issue, Result


def test_render_no_candidates() -> None:
    assert cli._render(()) == "no candidates ranked"


def test_render_numbers_the_list() -> None:
    out = cli._render(("a.py", "b.py"))
    assert out == "1. a.py\n2. b.py"


@pytest.mark.parametrize(
    ("outcome", "code"),
    [("success", 0), ("skipped", 0)],
)
def test_exit_code_maps_outcome(monkeypatch: pytest.MonkeyPatch, outcome: str, code: int) -> None:
    result = Result(outcome=outcome, issue=1, ranked=("a.py",), engine_used=False, detail="d")

    class _StubSearcher:
        def __init__(self, **kwargs: object) -> None:
            self.runner = lambda argv: '{"title": "t", "body": "b"}'

        def rank(self, issue: Issue, *, comment: bool = False) -> Result:
            return result

    monkeypatch.setattr(cli, "Searcher", _StubSearcher)
    assert cli.main(["rank", "--issue", "1", "--source", "."]) == code
