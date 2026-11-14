"""Post-processing of a sequential swap network.

truncate(g, history): the shortest prefix of `history` after which every pair
of labels has met (the initial configuration counts). Any such prefix is itself
a swap network, so truncation is always safe and never increases the count.
"""
from .verifier import SwapNetworkVerifier


def truncate(g, history):
    v = SwapNetworkVerifier(g)
    need = len(g) * (len(g) - 1) // 2
    if len(v.interacted_pairs) == need:
        return []
    for i, (a, b) in enumerate(history):
        v.swap_physical(a, b)
        if len(v.interacted_pairs) == need:
            return list(history[:i + 1])
    raise ValueError('history is not a complete swap network')
