"""Graph I/O, ASP backbone search, and the two paper-level legacy constructions."""
from __future__ import annotations

import re
import time
from pathlib import Path

import networkx as nx

from .verifier import SwapNetworkVerifier
from .leaf_insertion import LeafInsertion
from .swap_position import SwapAndPosition

ROOT = Path(__file__).resolve().parents[2]
ASP_ENCODING = ROOT / "ASP" / "Solvers" / "minimum_k_dominating_path.lp"
ASP_PORTFOLIO = ROOT / "ASP" / "Solvers" / "portfolio_bb_usc.txt"


def load_graph(path: str | Path) -> nx.Graph:
    """Read an ASP topology file containing #const n=... and edge(u,v) facts."""
    text = Path(path).read_text()
    match = re.search(r"#const\s+n\s*=\s*(\d+)", text)
    if not match:
        raise ValueError(f"{path}: missing '#const n=... .' declaration")
    n = int(match.group(1))
    graph = nx.Graph()
    graph.add_nodes_from(range(n))
    graph.add_edges_from((int(a), int(b)) for a, b in re.findall(r"edge\((\d+),(\d+)\)", text))
    if not nx.is_connected(graph):
        raise ValueError("The paper's constructions require a connected hardware graph.")
    return graph


def graph_facts(graph: nx.Graph) -> str:
    if set(graph) != set(range(len(graph))):
        raise ValueError("ASP input currently requires vertices labelled 0,...,n-1.")
    return f"#const n={len(graph)}.\n" + "\n".join(
        f"edge({u},{v})." for u, v in sorted(tuple(sorted(e)) for e in graph.edges())
    )


def valid_path(graph: nx.Graph, path: list[int], radius: int) -> bool:
    if not path or len(set(path)) != len(path):
        return False
    if any(not graph.has_edge(u, v) for u, v in zip(path, path[1:])):
        return False
    distances = {u: 0 for u in path}
    queue = list(path)
    for u in queue:
        for v in graph.neighbors(u):
            if v not in distances:
                distances[v] = distances[u] + 1
                queue.append(v)
    return len(distances) == len(graph) and max(distances.values(), default=0) <= radius


def solve_path(graph: nx.Graph, radius: int = 1, seconds: float = 600) -> dict:
    """Compute a minimum r-dominating path with the paper's ASP encoding."""
    if radius not in (1, 2):
        raise ValueError("This repository exposes only the paper's radii 1 and 2.")
    try:
        import clingo
    except ImportError as exc:
        raise RuntimeError("Clingo is required for ASP backbone search. Install requirements.txt.") from exc

    # The paper's experimental setup runs branch-and-bound and core-guided
    # optimization in parallel (two Clingo threads).
    control = clingo.Control([
        "--warn=none", "--seed=0", "-c", f"radius={radius}",
        "-t", "2", f"--configuration={ASP_PORTFOLIO}",
    ])
    control.load(str(ASP_ENCODING))
    control.add("base", [], graph_facts(graph))
    start_time = time.monotonic()
    control.ground([("base", [])])
    best = {}

    def on_model(model):
        shown = model.symbols(shown=True)
        starts = [s.arguments[0].number for s in shown if s.name == "start"]
        if not starts:
            return
        successor = {
            atom.arguments[0].number: atom.arguments[1].number
            for atom in shown if atom.name == "next"
        }
        path = [starts[0]]
        while path[-1] in successor:
            path.append(successor[path[-1]])
        best.update(path=path, size=len(path), cost=model.cost[0])

    with control.solve(on_model=on_model, async_=True) as handle:
        finished = handle.wait(max(0.001, seconds - (time.monotonic() - start_time)))
        if not finished:
            handle.cancel()
        result = handle.get()

    elapsed = time.monotonic() - start_time
    best.update(
        seconds=elapsed,
        optimal=bool(result.exhausted and result.satisfiable),
        status=("OPTIMUM" if result.exhausted and result.satisfiable
                else "UNSAT" if result.unsatisfiable else "TIMEOUT"),
    )
    if "path" in best:
        if not valid_path(graph, best["path"], radius):
            raise RuntimeError("ASP returned a path that failed independent validation.")
    return best


def insertion_grouping(graph: nx.Graph, path: list[int]):
    """Paper Algorithm 2: Swap-and-Position, then insert/group/acquaint leaves."""
    if not valid_path(graph, path, 1):
        raise ValueError("Insertion and Grouping requires a 1-dominating path.")
    verifier = SwapNetworkVerifier(graph)
    path = list(path)
    leaves = LeafInsertion(graph, path, verifier)
    stages = []

    count, path = SwapAndPosition.run(path, verifier)
    stages.append(count)
    count, path, loaded, start = leaves.insert_and_group_leaves()
    stages.append(count)
    count, block = SwapAndPosition.acquaint(path[start:start + loaded], verifier)
    path[start:start + loaded] = block
    stages.append(count)
    stages.append(leaves.full_walkthrough_remaining())

    if not verifier.verify_completeness()["is_complete"]:
        raise RuntimeError("Insertion and Grouping produced an incomplete network.")
    return verifier, stages


def delayed_insertion(graph: nx.Graph, path: list[int]):
    """Paper Section 5.2: radius-two delayed insertion with rotations/probes."""
    if not valid_path(graph, path, 2):
        raise ValueError("Delayed Insertion requires a 2-dominating path.")
    if len(graph) - len(path) > len(path):
        rotate = False
    else:
        rotate = True

    # The virtual caterpillar has the path as its spine and one virtual leaf
    # attached to each off-path vertex's selected anchor. The witness procedure
    # realizes virtual adjacencies on the physical graph by rotations (or probes
    # when the off-path set is too large to fit inside the backbone).
    virtual = nx.Graph()
    virtual.add_nodes_from(graph)
    virtual.add_edges_from(zip(path, path[1:]))
    routes = {}
    for vertex in sorted(set(graph) - set(path)):
        route = min(
            (nx.shortest_path(graph, vertex, anchor) for anchor in path),
            key=lambda route: (len(route), path.index(route[-1]), route),
        )
        virtual.add_edge(vertex, route[-1])
        routes[frozenset((vertex, route[-1]))] = route

    abstract, _ = insertion_grouping(virtual, path)
    physical = SwapNetworkVerifier(graph)
    state = {vertex: vertex for vertex in graph}
    virtual_edges = sorted(tuple(sorted(edge)) for edge in virtual.edges())

    def witness():
        moved = True
        while moved:
            moved = False
            for u, v in virtual_edges:
                pair = tuple(sorted((state[u], state[v])))
                if pair in physical.interacted_pairs:
                    continue
                route = routes.get(frozenset((u, v)), [u, v])
                hops = list(zip(route, route[1:]))[:-1]
                moves = hops if rotate else hops + list(reversed(hops))
                for a, b in moves:
                    physical.swap_physical(a, b)
                    state[a], state[b] = state[b], state[a]
                moved = moved or (rotate and len(hops) > 1)
                if pair not in physical.interacted_pairs:
                    raise RuntimeError("A virtual adjacency could not be witnessed physically.")

    witness()
    for u, v in abstract.swap_history:
        route = routes.get(frozenset((u, v)), [u, v])
        hops = list(zip(route, route[1:]))
        for a, b in hops + list(reversed(hops[:-1])):
            physical.swap_physical(a, b)
        state[u], state[v] = state[v], state[u]
        if physical.physical_to_logical != state:
            raise RuntimeError("Virtual and physical token states diverged.")
        witness()

    if not physical.verify_completeness()["is_complete"]:
        raise RuntimeError("Delayed Insertion produced an incomplete network.")
    return physical, {
        "rotations": rotate,
        "virtual_swaps": len(abstract.swap_history),
        "swaps": len(physical.swap_history),
    }


def replay(graph: nx.Graph, history):
    verifier = SwapNetworkVerifier(graph)
    for u, v in history:
        verifier.swap_physical(u, v)
    return verifier
