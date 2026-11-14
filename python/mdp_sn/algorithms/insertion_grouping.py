"""Algorithm 2: Insertion and Grouping on a 1-mDP."""
from ..core import insertion_grouping


def run(graph, path):
    verifier, stages = insertion_grouping(graph, path)
    return verifier.swap_history, {
        "algorithm": "Insertion and Grouping",
        "swap_and_position": stages[0],
        "insertion_and_grouping": stages[1],
        "leaf_acquaintance": stages[2],
        "residual_walkthrough": stages[3],
        "total": len(verifier.swap_history),
    }
