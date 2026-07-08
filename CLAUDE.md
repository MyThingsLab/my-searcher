# my-searcher — agent instructions

You are developing **my-searcher**, a MyThingsLab My[X] tool.

**Inherited rules:** obey [`./HARNESS.md`](./HARNESS.md) in full — the vendored
MyThingsLab build-harness rules. Do not restate or override them. Anything not
covered here defers to `HARNESS.md`, then `my-things-core/docs/CONVENTIONS.md`.

## This tool

- **Purpose:** indexes a repo's files and ranks the ones most relevant to a
  given issue — a reusable "which files matter here" step for later tools
  (MyGroomer, MyCoder) that need relevant-file context before acting.
- **The single Engine call:** required. Deterministic pre-work walks the repo
  tree (`git ls-files`), builds a lightweight index (path + top-level
  identifiers), and naive-scores every file by token overlap with the issue
  title/body to produce a candidate shortlist (default top 20). The Engine
  call reorders that shortlist by relevance — `EngineRequest.prompt` is the
  issue title/body plus the shortlist, `context={"candidates": [...],
  "issue_number": N}`; `EngineResult.data={"ranked": [path, ...]}` is a
  permutation of the shortlist, never new paths. Against `NoopEngine`, `data`
  is absent and the tool falls back to the deterministic pre-ranking order
  unchanged. If fewer than 2 candidates score, the Engine call is skipped
  entirely (nothing to rank).
- **Invariants / rules:** read-only over the repo tree — no edits, no
  `Workspace` worktree. No PR, no push. The only side effect is an optional
  `--comment`, which posts the ranked list to the issue as
  `Action(kind="bash", ...)` routed through `Policy` (default `ALLOW`, same as
  MyReporter's comment path). Writes exactly one `kind=search` ledger entry
  per run (`outcome=success|skipped`).
- **Backlog label:** `my-searcher`.
