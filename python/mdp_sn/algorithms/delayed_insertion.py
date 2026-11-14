"""Section 5.2: Delayed Insertion on a 2-mDP."""
from ..core import delayed_insertion


def run(graph, path):
    verifier, info = delayed_insertion(graph, path)
    return verifier.swap_history, {
        **info,
        "algorithm": "Delayed Insertion",
        "total": len(verifier.swap_history),
    }
