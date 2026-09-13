from pathlib import Path

from conftest import make_repo
from mysearcher.indexer import shortlist


def test_graph_traversal_boosts_connected_caller(tmp_path: Path) -> None:
    checkout_code = (
        "from src.core import process_payment\n"
        "def submit_order():\n"
        "    return process_payment(100)\n"
    )
    repo = make_repo(
        tmp_path,
        {
            "src/core.py": "def process_payment(amount: int) -> bool:\n    return True\n",
            "src/checkout.py": checkout_code,
            "src/unrelated.py": "def unrelated_service():\n    pass\n",
        },
    )

    # Issue specifically mentions process_payment
    results = shortlist(repo, "Crash in process_payment", "Payment fails under load", top=10)

    # src/core.py is top; checkout.py (caller via graph) ranks ahead of unrelated
    assert results[0] == "src/core.py"
    assert "src/checkout.py" in results
    assert results.index("src/checkout.py") < results.index("src/unrelated.py")
