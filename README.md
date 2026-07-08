# my-searcher

[![CI](https://github.com/MyThingsLab/my-searcher/actions/workflows/ci.yml/badge.svg)](https://github.com/MyThingsLab/my-searcher/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/MyThingsLab/my-searcher/branch/main/graph/badge.svg)](https://codecov.io/gh/MyThingsLab/my-searcher) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Indexes a repo's files and ranks the ones most relevant to a given issue — a
reusable "which files matter here" step, designed for reuse by later
[MyThingsLab](../mythings-core) tools (MyGroomer, MyCoder) that need
relevant-file context before acting.

## How it works

Deterministic pre-work:

1. Walk the repo tree via `git ls-files`, building a lightweight index: path
   + top-level identifiers (function/class names via `ast.parse` for `.py`;
   a best-effort grep of exported symbols for other languages).
2. Tokenize the issue title/body.
3. Score every indexed file by naive term overlap between issue tokens and
   {path components ∪ identifier names}.
4. Take the top N (default 20) by score as the candidate shortlist — this
   bounds the Engine prompt and keeps the tool cheap even on a large repo.
   If nothing scores above zero, fall back to the most-recently-modified
   files rather than an empty shortlist.

If the shortlist has at least 2 candidates, the **one Engine call** reorders
it by relevance — a permutation of the shortlist, never a new path (anything
the model invents outside the shortlist is dropped; anything it silently
drops is appended back, preserving order). Against `NoopEngine`, the reply is
empty and the deterministic pre-ranking order is returned unchanged.

No `Workspace` worktree — read-only over the repo tree, no edits, no PR. The
only side effect is an optional `--comment`, which posts the ranked list to
the issue as `Action(kind="bash", ...)` routed through `Policy` (`ALLOW` by
default). Writes exactly one `kind=search` ledger entry per run.

## Usage

```bash
mysearcher rank --issue 12 --source . [--repo owner/name] [--top 20] [--json]
mysearcher rank --issue 12 --repo owner/name --comment   # also posts the ranked list
mysearcher rank --issue 12 --engine claude-cli           # real Engine reorder
```

## In the fleet loop

Standalone today (no other tool calls it yet) — a building block designed
ahead of MyGroomer/MyCoder per the
[design doc](../mythings-core/docs/tools/my-searcher.md). See the
[org README](../README.md) for how the shipped tools chain together.

## Install (development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ../mythings-core -e ".[dev]"
pytest
```

## License

MIT — see [`LICENSE`](LICENSE).
