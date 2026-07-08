from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from mythings.engine import Engine, EngineRequest, NoopEngine
from mythings.github import Runner, _gh
from mythings.isolation import in_github_actions
from mythings.ledger import Ledger
from mythings.policy import ALLOW, Action, Decision, Policy, PolicyResult

from mysearcher.indexer import shortlist

_ENGINE_SYSTEM = (
    "You rank a shortlist of candidate files by relevance to an issue. Reorder "
    "the given paths only -- never invent a path that isn't in the shortlist. "
    'Reply with only a JSON object: {"ranked": ["<path>", ...]}, nothing else.'
)


class _AllowPolicy:
    def evaluate(self, action: Action) -> PolicyResult:
        return ALLOW


@dataclass(frozen=True)
class Result:
    outcome: str  # success | skipped
    issue: int
    ranked: tuple[str, ...]
    engine_used: bool
    detail: str
    comment_url: str | None = None


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    body: str = ""


class Searcher:
    def __init__(
        self,
        *,
        repo_path: str | Path,
        ledger: Ledger,
        repo: str | None = None,
        runner: Runner = _gh,
        engine: Engine | None = None,
        policy: Policy | None = None,
        top: int = 20,
    ) -> None:
        self.repo_path = Path(repo_path)
        self.ledger = ledger
        self.repo = repo
        self.runner = runner
        self.engine: Engine = engine or NoopEngine()
        self.policy: Policy = policy or _AllowPolicy()
        self.top = top

    def rank(self, issue: Issue, *, comment: bool = False) -> Result:
        candidates = shortlist(self.repo_path, issue.title, issue.body, top=self.top)
        ranked = self._reorder(candidates, issue) if len(candidates) >= 2 else candidates
        outcome = "success" if candidates else "skipped"
        detail = f"ranked {len(ranked)} candidate(s) for issue #{issue.number}"
        comment_url = self._comment(issue.number, ranked) if comment else None
        result = Result(
            outcome=outcome,
            issue=issue.number,
            ranked=tuple(ranked),
            engine_used=bool(candidates) and len(candidates) >= 2,
            detail=detail,
            comment_url=comment_url,
        )
        self._record(result, candidates)
        return result

    def _reorder(self, candidates: list[str], issue: Issue) -> list[str]:
        prompt = (
            f"Issue #{issue.number}: {issue.title}\n\n{issue.body}\n\n"
            f"Candidates:\n" + "\n".join(candidates)
        )
        reply = self.engine.run(
            EngineRequest(
                prompt=prompt,
                system=_ENGINE_SYSTEM,
                context={"candidates": candidates, "issue_number": issue.number},
            )
        )
        ranked = _parse_ranked(reply.text, candidates)
        return ranked if ranked is not None else candidates

    def _comment(self, issue: int, ranked: list[str]) -> str | None:
        if self.repo is None or not ranked:
            return None
        body = "Files ranked most relevant to this issue:\n\n" + "\n".join(
            f"{i}. `{path}`" for i, path in enumerate(ranked, start=1)
        )
        argv = ["issue", "comment", str(issue), "--repo", self.repo, "--body", body]
        action = Action(kind="bash", payload={"command": "gh " + " ".join(argv[:3])})
        if self.policy.evaluate(action).under(unattended=in_github_actions()) is not Decision.ALLOW:
            return None
        return self.runner(argv).strip() or None

    def _record(self, result: Result, candidates: list[str]) -> None:
        self.ledger.record(
            tool="mysearcher",
            kind="search",
            outcome=result.outcome,
            detail=result.detail,
            issue=result.issue,
            candidates=candidates,
            ranked=list(result.ranked),
            comment_url=result.comment_url,
        )


def _parse_ranked(text: str, candidates: list[str]) -> list[str] | None:
    if not text:
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    ranked = obj.get("ranked") if isinstance(obj, dict) else None
    if not isinstance(ranked, list):
        return None
    # The model may only reorder the shortlist -- drop anything it invented,
    # then append any candidate it silently dropped, preserving order.
    valid = [path for path in ranked if path in candidates]
    seen = set(valid)
    valid += [path for path in candidates if path not in seen]
    return valid or None
