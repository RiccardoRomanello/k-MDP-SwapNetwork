"""Algorithm 4: Vines, the early-insertion construction for 2-mDPs."""
from __future__ import annotations

import itertools
from collections import deque

from ..core import delayed_insertion, replay
from ..postprocess import truncate
from ..swap_position import SwapAndPosition
from .early_leaves_insertion import CountingVerifier, sp_schedule


def breadth_first_forest(graph, path):
    """Root a deterministic BFS forest at the ordered backbone."""
    distance, parent, root = {}, {}, {}
    queue = deque()
    for i, vertex in enumerate(path):
        distance[vertex], root[vertex] = 0, i
        queue.append(vertex)
    while queue:
        u = queue.popleft()
        for v in sorted(graph[u], key=str):
            if v not in distance:
                distance[v], parent[v], root[v] = distance[u] + 1, u, root[u]
                queue.append(v)
    if len(distance) != len(graph):
        raise ValueError("The backbone does not reach every vertex.")
    return distance, parent, root


def _gather_plan(path, distance, parent, root, tokens, start):
    """Plan a minimum-move gathering of all off-path labels into one path block."""
    position = {vertex: i for i, vertex in enumerate(path)}
    count = len(tokens)
    occupied = {vertex: label for label, vertex in tokens}
    source = {label: root[vertex] for label, vertex in tokens}
    depth = {label: distance[vertex] for label, vertex in tokens}
    where = {label: vertex for label, vertex in tokens}

    groups = {}
    for label, _ in tokens:
        groups.setdefault(source[label], []).append(label)

    order, target_start = [], start
    for anchor in sorted(groups):
        group = groups[anchor]
        move_left = max(0, min(len(group), anchor - target_start))
        on_path = [label for label in group if depth[label] == 0]
        off_path = sorted(
            (label for label in group if depth[label] > 0),
            key=lambda label: (depth[label], str(label)),
        )
        if on_path and move_left > 0:
            sequence = on_path + off_path[:move_left - 1] + sorted(
                off_path[move_left - 1:], key=lambda label: (-depth[label], str(label))
            )
        elif on_path:
            sequence = sorted(off_path, key=lambda label: (-depth[label], str(label))) + on_path
        else:
            sequence = off_path[:move_left] + sorted(
                off_path[move_left:], key=lambda label: (-depth[label], str(label))
            )
        order.extend(sequence)
        target_start += len(group)

    target = {label: start + i for i, label in enumerate(order)}
    left = sorted(
        (label for label in order if target[label] < source[label]),
        key=lambda label: target[label],
    )
    right = sorted(
        (label for label in order if target[label] > source[label]),
        key=lambda label: -target[label],
    )
    stay = [label for label in order if target[label] == source[label]]
    moves = []

    def step(label, next_vertex):
        if next_vertex in occupied:
            return False
        current = where[label]
        del occupied[current]
        occupied[next_vertex] = label
        where[label] = next_vertex
        moves.append((current, next_vertex))
        return True

    for label in left + right + stay:
        while where[label] not in position:
            if not step(label, parent[where[label]]):
                return None
        while position[where[label]] != target[label]:
            i = position[where[label]]
            j = i + (1 if target[label] > i else -1)
            if not step(label, path[j]):
                return None
    return moves


def vines(graph, path):
    """Run Algorithm 4. If |V\\P|>|P|, use Section 5.2's delayed insertion."""
    path = list(path)
    if len(graph) - len(path) > len(path):
        verifier, info = delayed_insertion(graph, path)
        history = verifier.swap_history
        info = dict(info)
        info.update(algorithm="Vines", fallback="Delayed Insertion")
        return history, info

    distance, parent, root = breadth_first_forest(graph, path)
    position = {vertex: i for i, vertex in enumerate(path)}
    children = {}
    for child, p in parent.items():
        children.setdefault(p, []).append(child)
    for p in children:
        children[p].sort(key=str)

    verifier = CountingVerifier(graph)
    label_at, location = verifier.physical_to_logical, verifier.logical_to_physical
    pending = {vertex for vertex in graph if distance[vertex] > 0}
    seen_ends = {label: set() for label in graph}
    for label in graph:
        if location[label] == path[0]:
            seen_ends[label].add(0)
        if location[label] == path[-1]:
            seen_ends[label].add(1)

    def complete(label):
        return len(seen_ends[label]) == 2

    used_slots = set()
    slot_at = list(range(len(path)))
    stats = {"rotations": 0, "insertions": 0, "shifts": 0}

    def rotations():
        # A far leaf is rotated towards its parent unless a complete node is
        # currently using that vine for an insertion.
        for far_vertex in sorted(
            (v for v in graph if distance[v] >= 2),
            key=lambda v: (distance[v], str(v)),
        ):
            far_label = label_at[far_vertex]
            if far_label not in pending:
                continue
            parent_vertex = far_vertex
            while distance[parent_vertex] > 1:
                parent_vertex = parent[parent_vertex]
            anchor = parent[parent_vertex]
            anchor_label = label_at[anchor]
            entering_vine = None
            if complete(anchor_label) and anchor_label not in pending:
                anchor_index = position[anchor]
                if slot_at[anchor_index] not in used_slots:
                    vines_here = children.get(anchor, [])
                    entering_vine = next(
                        (v for v in vines_here if label_at[v] in pending), None
                    )
            pair = tuple(sorted((anchor_label, far_label)))
            if pair not in verifier.interacted_pairs and parent_vertex != entering_vine:
                verifier.swap_physical(far_vertex, parent_vertex)
                stats["rotations"] += 1

    def settle():
        rotations()
        changed = True
        while changed:
            changed = False
            # Shifts: a parked label moves down to let the next label climb.
            for vertex in sorted(parent, key=lambda v: (distance[v], str(v))):
                if label_at[vertex] in pending:
                    continue
                for child in children.get(vertex, []):
                    if label_at[child] in pending:
                        verifier.swap_physical(vertex, child)
                        stats["shifts"] += 1
                        changed = True
                        break
            # Insertions: a complete backbone label is replaced by a vine label.
            for leaf_vertex in sorted(
                (v for v in graph if distance[v] == 1), key=str
            ):
                label = label_at[leaf_vertex]
                if label not in pending:
                    continue
                anchor = parent[leaf_vertex]
                anchor_index = position[anchor]
                displaced = label_at[path[anchor_index]]
                if (displaced in pending or slot_at[anchor_index] in used_slots
                        or not complete(displaced)):
                    continue
                verifier.swap_physical(leaf_vertex, path[anchor_index])
                pending.discard(label)
                used_slots.add(slot_at[anchor_index])
                stats["insertions"] += 1
                changed = True

    settle()
    for i, j in sp_schedule(len(path)):
        verifier.swap_physical(path[i], path[j])
        slot_at[i], slot_at[j] = slot_at[j], slot_at[i]
        for label in (label_at[path[i]], label_at[path[j]]):
            if location[label] == path[0]:
                seen_ends[label].add(0)
            if location[label] == path[-1]:
                seen_ends[label].add(1)
        settle()

    stats["swap_and_position"] = len(verifier.swap_history)
    off_path_labels = sorted(
        (label for label in graph if distance[label] > 0), key=str
    )
    missing = {
        tuple(sorted(pair))
        for pair in itertools.combinations(graph, 2)
    } - verifier.interacted_pairs
    if any(a not in off_path_labels or b not in off_path_labels for a, b in missing):
        raise RuntimeError("Vines invariant failed: a backbone label still has an unmet pair.")

    if off_path_labels:
        tokens = [(label, location[label]) for label in off_path_labels]
        best = None
        for start in range(len(path) - len(off_path_labels) + 1):
            moves = _gather_plan(path, distance, parent, root, tokens, start)
            if moves is not None and (best is None or len(moves) < len(best[0])):
                best = (moves, start)
        if best is None:
            raise RuntimeError("Vines could not gather the off-path labels into the backbone.")
        for u, v in best[0]:
            verifier.swap_physical(u, v)
        start = best[1]
        block = [label_at[path[i]] for i in range(start, start + len(off_path_labels))]
        if set(block) != set(off_path_labels):
            raise RuntimeError("Vines gathering produced an incorrect block.")
        acquaint, _ = SwapAndPosition.acquaint(block, verifier)
        stats["gathering"] = len(best[0])
        stats["acquaintance"] = acquaint
    else:
        stats["gathering"] = stats["acquaintance"] = 0

    if not verifier.verify_completeness()["is_complete"]:
        raise RuntimeError("Vines produced an incomplete network.")
    history = truncate(graph, verifier.swap_history)
    stats.update(total=len(verifier.swap_history), truncated=len(history),
                 algorithm="Vines")
    if not replay(graph, history).verify_completeness()["is_complete"]:
        raise RuntimeError("Vines failed independent replay.")
    return history, stats
