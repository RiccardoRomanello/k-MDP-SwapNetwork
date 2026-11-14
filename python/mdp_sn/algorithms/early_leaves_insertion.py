"""Algorithm 3: Early Leaves Insertion for a minimum dominating path."""
import itertools
import networkx as nx

from ..core import insertion_grouping, replay
from ..verifier import SwapNetworkVerifier
from ..leaf_insertion import LeafInsertion
from ..swap_position import SwapAndPosition
from ..postprocess import truncate


class CountingVerifier(SwapNetworkVerifier):
    """Verifier that also counts, for every label, how many labels it has met."""
    def __init__(self, graph):
        self.met = {v: 0 for v in graph}
        super().__init__(graph)

    def _record_interaction(self, a, b):
        if a != b:
            q = tuple(sorted((a, b)))
            if q not in self.interacted_pairs:
                self.interacted_pairs.add(q)
                self.met[a] += 1
                self.met[b] += 1

    def done(self, a):
        return self.met[a] == self.n - 1


def sp_schedule(p):
    """Swap-and-Position on positions 0..p-1, as a list of position pairs."""
    if p < 2:
        return []
    v = SwapNetworkVerifier(nx.path_graph(p))
    SwapAndPosition.run(list(range(p)), v)
    return [tuple(e) for e in v.swap_history]


def slot_final_positions(p):
    slot = list(range(p))
    for i, j in sp_schedule(p):
        slot[i], slot[j] = slot[j], slot[i]
    return {s: x for x, s in enumerate(slot)}


def anchors_of(g, P):
    h = LeafInsertion(g, list(P), SwapNetworkVerifier(g))
    return {leaf: i for i, s in enumerate(h.leaves_per_node) for leaf in s}


# ----------------------------------------------------------------- transport
def transport_plan(spine_len, tokens, s, outside_first=True):
    """Abstract feasibility/cost of moving leaf tokens into block [s, s+m).

    tokens: list of (source position, outside: bool, id).  Leaves move only by
    swapping with non-leaf labels; an outside leaf enters at its anchor, which
    must hold a non-leaf label at that moment.  Returns (cost, moves) or None.
    moves: list of ('enter', id) | ('step', id, +1/-1), in execution order.
    """
    m = len(tokens)
    order = sorted(tokens, key=lambda t: (t[0], (not t[1]) if outside_first else t[1], str(t[2])))
    target = {t[2]: s + k for k, t in enumerate(order)}
    pos = {t[2]: (t[0] if not t[1] else None) for t in tokens}
    anchor = {t[2]: t[0] for t in tokens}
    occ = {}
    for tid, x in pos.items():
        if x is not None:
            if x in occ:
                return None
            occ[x] = tid
    left = sorted([t for t in tokens if target[t[2]] < t[0]], key=lambda t: target[t[2]])
    right = sorted([t for t in tokens if target[t[2]] > t[0]], key=lambda t: -target[t[2]])
    stay = [t for t in tokens if target[t[2]] == t[0]]
    moves = []
    for t in left + right + stay:
        tid = t[2]
        if pos[tid] is None:
            a = anchor[tid]
            if a in occ:
                return None
            occ[a] = tid; pos[tid] = a; moves.append(('enter', tid))
        while pos[tid] != target[tid]:
            d = 1 if target[tid] > pos[tid] else -1
            nxt = pos[tid] + d
            if nxt in occ:
                return None
            del occ[pos[tid]]; occ[nxt] = tid; pos[tid] = nxt; moves.append(('step', tid, d))
    return len(moves), moves


def best_transport(spine_len, tokens, s_candidates):
    best = None
    for s in s_candidates:
        if not 0 <= s <= spine_len - len(tokens):
            continue
        for of in (True, False):
            r = transport_plan(spine_len, tokens, s, of)
            if r is not None and (best is None or r[0] < best[0]):
                best = (r[0], r[1], s, of)
    return best


# ----------------------------------------------------------------- pipeline
def early_pipeline(g, P, anchors, block_start):
    """Return (verifier, info) for the early-insertion pipeline, or None if m > p
    or if transport is infeasible."""
    P = list(P)
    p = len(P)
    anchors = anchors if anchors is not None else anchors_of(g, P)
    leaves = sorted(anchors, key=str)
    m = len(leaves)
    if m > p:
        return None
    v = CountingVerifier(g)
    lab = v.physical_to_logical
    pos_of = {u: i for i, u in enumerate(P)}
    final = slot_final_positions(p)
    # sorted matching leaf -> target in the old block
    s0 = block_start
    by_anchor = sorted(leaves, key=lambda l: (anchors[l], str(l)))
    target = {l: s0 + k for k, l in enumerate(by_anchor)}
    inv = {x: sl for sl, x in final.items()}
    want_slot = {l: inv[target[l]] for l in leaves}
    slot_at = list(range(p))          # slot_at[position] = slot id
    outside = set(leaves)             # leaf vertices whose original label is still there
    used_slot = set()
    inserted = {}

    def try_insert(t):
        for l in sorted(outside, key=str):
            a = anchors[l]
            sl = slot_at[a]
            if want_slot[l] != sl:
                continue
            if sl in used_slot:
                continue
            here = lab[P[a]]
            if here in leaves or not v.done(here):
                continue
            v.swap_physical(l, P[a])
            outside.discard(l); used_slot.add(sl); inserted[l] = (t, sl)

    sched = sp_schedule(p)
    try_insert(0)
    for t, (i, j) in enumerate(sched, 1):
        v.swap_physical(P[i], P[j])
        slot_at[i], slot_at[j] = slot_at[j], slot_at[i]
        try_insert(t)
    c_sp = len(v.swap_history)
    # only leaf-leaf pairs may be unmet now
    leaf_labels = set(leaves)            # labels = original leaf vertex ids
    for q in itertools.combinations(g, 2):
        tq = tuple(sorted(q))
        if tq not in v.interacted_pairs:
            assert tq[0] in leaf_labels and tq[1] in leaf_labels, ('non leaf-leaf pair unmet', tq)
    # transport into a block
    tokens = []
    for l in leaves:
        u = v.logical_to_physical[l]
        if u in pos_of:
            tokens.append((pos_of[u], False, l))
        else:
            tokens.append((anchors[l], True, l))
    if m:
        cand = range(0, p - m + 1)
        bt = best_transport(p, tokens, cand)
        if bt is None:
            return None
        _, moves, s, _ = bt
        for mv in moves:
            l = mv[1]
            if mv[0] == 'enter':
                v.swap_physical(l, P[anchors[l]])
            else:
                x = pos_of[v.logical_to_physical[l]]
                v.swap_physical(P[x], P[x + mv[2]])
        c_tr = len(v.swap_history) - c_sp
        block = [lab[P[x]] for x in range(s, s + m)]
        assert set(block) == leaf_labels
        c_acq, _ = SwapAndPosition.acquaint(block, v)
    else:
        c_tr = c_acq = 0
        s = 0
    assert v.verify_completeness()['is_complete']
    hist = truncate(g, v.swap_history)
    info = dict(sp=c_sp, transport=c_tr, acquaint=c_acq, total=len(v.swap_history), truncated=len(hist),
                early=len(inserted), late=m - len(inserted), m=m, p=p)
    return hist, info



def early_leaves_insertion(graph, path):
    """Run Algorithm 3 for every possible target block and keep the shortest.

    If the off-path set is larger than the path, the paper's Algorithm 3
    precondition is not met and Algorithm 2 is used, as specified in Section 4.5.
    """
    path = list(path)
    anchors = anchors_of(graph, path)
    m, p = len(anchors), len(path)
    if m > p:
        verifier, stages = insertion_grouping(graph, path)
        history = truncate(graph, verifier.swap_history)
        return history, {"fallback": "Insertion and Grouping", "stages": stages,
                         "total": len(history), "truncated": len(history)}

    starts = range(max(1, p - m + 1))
    candidates = []
    for start in starts:
        result = early_pipeline(graph, path, anchors=anchors, block_start=start)
        if result is not None:
            history, info = result
            candidates.append((len(history), start, history, info))
    if not candidates:
        raise RuntimeError("Early Leaves Insertion found no feasible target block.")
    _, start, history, info = min(candidates, key=lambda item: (item[0], item[1]))
    if not replay(graph, history).verify_completeness()["is_complete"]:
        raise RuntimeError("Early Leaves Insertion failed independent replay.")
    info = dict(info)
    info.update(target_block_start=start, candidate_blocks=len(candidates),
                algorithm="Early Leaves Insertion")
    return history, info
