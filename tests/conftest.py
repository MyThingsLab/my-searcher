from __future__ import annotations

from pathlib import Path

import pytest

# Shared fakes come from mythings.testing (plain imports; aliased fixture
# re-export + getfixturevalue wrapper per core docs/CONVENTIONS.md).
from mythings.testing import FakeGh, make_git_repo
from mythings.testing import clean_git_env as _shared_clean_git_env  # noqa: F401


@pytest.fixture(autouse=True)
def _clean_git_env(request: pytest.FixtureRequest) -> None:
    request.getfixturevalue("_shared_clean_git_env")


def make_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    return make_git_repo(tmp_path, files=files).path


def fake_gh(comment_url: str = "https://github.com/owner/name/issues/1#comment") -> FakeGh:
    return FakeGh({("issue", "comment"): comment_url + "\n"})
