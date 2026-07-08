from __future__ import annotations

import argparse
import json
from pathlib import Path

from mythings.engine import ClaudeCLIEngine, Engine, NoopEngine
from mythings.github import Runner
from mythings.ledger import Ledger

from mysearcher.searcher import Issue, Searcher

_ENGINE_NAMES = ("noop", "claude-cli")


def build_engine(name: str, *, model: str | None = None) -> Engine:
    if name == "claude-cli":
        return ClaudeCLIEngine(model=model)
    return NoopEngine()


def _fetch_issue(number: int, repo: str | None, runner: Runner) -> Issue:
    argv = ["issue", "view", str(number), "--json", "title,body"]
    if repo:
        argv += ["--repo", repo]
    obj = json.loads(runner(argv))
    return Issue(number=number, title=obj["title"], body=obj.get("body") or "")


def _render(ranked: tuple[str, ...]) -> str:
    if not ranked:
        return "no candidates ranked"
    return "\n".join(f"{i}. {path}" for i, path in enumerate(ranked, start=1))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mysearcher",
        description="Rank a repo's files by relevance to an issue.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    rank = sub.add_parser("rank", help="rank files relevant to an issue")
    rank.add_argument("--issue", type=int, required=True)
    rank.add_argument("--repo", help="GitHub slug owner/name")
    rank.add_argument("--source", type=Path, default=Path.cwd(), help="local checkout to index")
    rank.add_argument("--top", type=int, default=20)
    rank.add_argument(
        "--comment", action="store_true", help="also post the ranked list to the issue"
    )
    rank.add_argument("--json", action="store_true")
    rank.add_argument("--ledger", type=Path, default=Path(".mythings/ledger.jsonl"))
    rank.add_argument("--engine", choices=sorted(_ENGINE_NAMES), default="noop")
    rank.add_argument("--engine-model", help="model for --engine claude-cli")

    args = parser.parse_args(argv)
    engine = build_engine(args.engine, model=args.engine_model)

    searcher = Searcher(
        repo_path=args.source,
        ledger=Ledger(args.ledger),
        repo=args.repo,
        engine=engine,
        top=args.top,
    )
    issue = _fetch_issue(args.issue, args.repo, searcher.runner)
    result = searcher.rank(issue, comment=args.comment)

    if args.json:
        print(
            json.dumps(
                {
                    "outcome": result.outcome,
                    "issue": result.issue,
                    "ranked": list(result.ranked),
                    "comment_url": result.comment_url,
                }
            )
        )
    else:
        print(_render(result.ranked))
    return 0 if result.outcome != "failure" else 1


if __name__ == "__main__":
    raise SystemExit(main())
