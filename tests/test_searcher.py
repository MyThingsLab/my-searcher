from __future__ import annotations

import json
from pathlib import Path

from mythings.engine import EngineRequest, EngineResult, NoopEngine
from mythings.ledger import Ledger
from mythings.policy import Action, Decision, PolicyResult

from conftest import fake_gh, make_repo
from mysearcher.searcher import Issue, Searcher


class ScriptedEngine:
    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.requests: list[EngineRequest] = []

    def run(self, request: EngineRequest) -> EngineResult:
        self.requests.append(request)
        return EngineResult(text=self._reply)


class DenyPolicy:
    def evaluate(self, action: Action) -> PolicyResult:
        return PolicyResult(Decision.DENY, reason="no", rule="test")


def _repo(tmp_path: Path) -> Path:
    return make_repo(
        tmp_path,
        {
            "src/widget.py": "class WidgetParser:\n    def parse(self):\n        pass\n",
            "src/other.py": "def unrelated():\n    pass\n",
        },
    )


def test_rank_falls_back_to_deterministic_order_against_noop_engine(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    searcher = Searcher(repo_path=repo, ledger=ledger, engine=NoopEngine())
    result = searcher.rank(Issue(number=1, title="WidgetParser is broken", body=""))
    assert result.outcome == "success"
    assert result.ranked[0] == "src/widget.py"
    entries = list(ledger)
    assert entries[-1].kind == "search"
    assert entries[-1].data["issue"] == 1


def test_rank_uses_engine_reorder_when_valid_json(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    engine = ScriptedEngine(json.dumps({"ranked": ["src/other.py", "src/widget.py"]}))
    searcher = Searcher(repo_path=repo, ledger=ledger, engine=engine)
    result = searcher.rank(Issue(number=2, title="WidgetParser is broken", body=""))
    assert result.ranked[0] == "src/other.py"
    assert result.engine_used


def test_engine_cannot_invent_paths_outside_the_shortlist(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    engine = ScriptedEngine(json.dumps({"ranked": ["not/a/real/file.py", "src/widget.py"]}))
    searcher = Searcher(repo_path=repo, ledger=ledger, engine=engine)
    result = searcher.rank(Issue(number=3, title="WidgetParser is broken", body=""))
    assert "not/a/real/file.py" not in result.ranked
    assert set(result.ranked) == {"src/widget.py", "src/other.py"}


def test_engine_reply_that_is_not_json_falls_back(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    engine = ScriptedEngine("not json")
    searcher = Searcher(repo_path=repo, ledger=ledger, engine=engine)
    result = searcher.rank(Issue(number=4, title="WidgetParser is broken", body=""))
    assert result.ranked[0] == "src/widget.py"


def test_comment_posts_ranked_list_when_requested(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    fake = fake_gh()
    searcher = Searcher(
        repo_path=repo, ledger=ledger, repo="owner/name", runner=fake, engine=NoopEngine()
    )
    result = searcher.rank(Issue(number=5, title="WidgetParser is broken", body=""), comment=True)
    assert result.comment_url is not None
    assert fake.calls[0][:2] == ["issue", "comment"]


def test_comment_skipped_without_repo(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    searcher = Searcher(repo_path=repo, ledger=ledger, engine=NoopEngine())
    result = searcher.rank(Issue(number=6, title="WidgetParser is broken", body=""), comment=True)
    assert result.comment_url is None


def test_comment_denied_by_policy_is_not_posted(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    fake = fake_gh()
    searcher = Searcher(
        repo_path=repo,
        ledger=ledger,
        repo="owner/name",
        runner=fake,
        engine=NoopEngine(),
        policy=DenyPolicy(),
    )
    result = searcher.rank(Issue(number=7, title="WidgetParser is broken", body=""), comment=True)
    assert result.comment_url is None
    assert fake.calls == []
