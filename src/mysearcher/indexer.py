from __future__ import annotations

import ast
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


@dataclass(frozen=True)
class IndexedFile:
    path: str
    identifiers: tuple[str, ...]


def tokenize(text: str) -> set[str]:
    return {tok.lower() for tok in _TOKEN_RE.findall(text) if tok}


def _python_identifiers(source: str) -> tuple[str, ...]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ()
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.append(node.name)
    return tuple(names)


def _grep_identifiers(source: str) -> tuple[str, ...]:
    # Best-effort, non-Python: any bare word that looks like an exported
    # symbol (function/class-ish token following a common declaration
    # keyword). Not exhaustive by design -- see docs/tools/my-searcher.md.
    keywords = ("function", "class", "def", "const", "struct", "interface")
    found: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        for kw in keywords:
            if stripped.startswith(kw + " "):
                rest = stripped[len(kw) + 1 :]
                match = _TOKEN_RE.match(rest)
                if match:
                    found.append(match.group(0))
    return tuple(found)


def list_files(repo: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in proc.stdout.splitlines() if line]


def build_index(repo: Path) -> list[IndexedFile]:
    index: list[IndexedFile] = []
    for relpath in list_files(repo):
        full = repo / relpath
        if not full.is_file():
            continue
        try:
            source = full.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            index.append(IndexedFile(path=relpath, identifiers=()))
            continue
        identifiers = (
            _python_identifiers(source) if relpath.endswith(".py") else _grep_identifiers(source)
        )
        index.append(IndexedFile(path=relpath, identifiers=identifiers))
    return index


def score_files(index: list[IndexedFile], issue_tokens: set[str]) -> list[tuple[str, int]]:
    scored: list[tuple[str, int]] = []
    for entry in index:
        path_tokens = tokenize(entry.path)
        identifier_tokens = {tok.lower() for name in entry.identifiers for tok in tokenize(name)}
        overlap = len(issue_tokens & (path_tokens | identifier_tokens))
        scored.append((entry.path, overlap))
    return scored


def shortlist(repo: Path, issue_title: str, issue_body: str, *, top: int = 20) -> list[str]:
    index = build_index(repo)
    issue_tokens = tokenize(issue_title) | tokenize(issue_body)
    scored = score_files(index, issue_tokens)
    scores: dict[str, float] = {path: float(score) for path, score in scored}

    # Augment relevance with deterministic graph traversal (my-searcher#9)
    try:
        from mythings.graph import CodebaseGraph, MarkdownExtractor, PythonAstExtractor

        cached_db = repo / ".mythings" / "graph.sqlite"
        if cached_db.exists():
            graph = CodebaseGraph(cached_db)
        else:
            graph = CodebaseGraph.in_memory()
            PythonAstExtractor(repo_root=repo).index_repo(graph)
            MarkdownExtractor(repo_root=repo).index_docs(graph)

        seed_nodes = []
        for token in issue_tokens:
            if len(token) >= 3:
                for s in graph.find_symbols(token):
                    seed_nodes.append(s)

        seed_ids = [s.id for s in seed_nodes]
        if seed_ids:
            # 1-hop neighbors get +3.0 boost (callers, callees, types, governing docs)
            hop1_nodes, _ = graph.k_hop_subgraph(seed_ids, k=1)
            for n in hop1_nodes:
                if n.path:
                    scores[n.path] = scores.get(n.path, 0.0) + 3.0

            # 2-hop neighbors get +1.0 boost
            hop2_nodes, _ = graph.k_hop_subgraph(seed_ids, k=2)
            hop1_paths = {h.path for h in hop1_nodes}
            for n in hop2_nodes:
                if n.path and n.path not in hop1_paths:
                    scores[n.path] = scores.get(n.path, 0.0) + 1.0
    except Exception:
        pass

    if issue_tokens and any(score > 0 for score in scores.values()):
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        return [path for path, _ in ranked[:top]]
    # Nothing scored above zero (or the issue carried no usable tokens): fall
    # back to most-recently-modified files rather than an empty shortlist --
    # a weak ranking is still a usable result, per the design doc's edge case.
    by_mtime = sorted(index, key=lambda entry: (repo / entry.path).stat().st_mtime, reverse=True)
    return [entry.path for entry in by_mtime[:top]]
