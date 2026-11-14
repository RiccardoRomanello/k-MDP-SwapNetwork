import itertools
import networkx as nx

class SwapNetworkVerifier:
    """Exact logical/physical simulation; reject every non-edge operation."""
    def __init__(self, graph):
        self.graph = graph.copy()
        self.n = len(graph)
        self.logical_to_physical = {v: v for v in graph}
        self.physical_to_logical = {v: v for v in graph}
        self.interacted_pairs = set()
        self.swap_history = []
        self.visited = {v: {v} for v in graph}
        self.register_initial_interactions()

    def register_initial_interactions(self):
        for u, v in self.graph.edges():
            self._record_interaction(self.physical_to_logical[u], self.physical_to_logical[v])

    def _record_interaction(self, a, b):
        if a != b:
            self.interacted_pairs.add(tuple(sorted((a, b))))

    def swap(self, a, b):
        if a == b:
            raise ValueError('A SWAP must have distinct operands')
        u, v = self.logical_to_physical[a], self.logical_to_physical[b]
        if not self.graph.has_edge(u, v):
            raise ValueError(f'Illegal physical SWAP {(u,v)} for labels {(a,b)}')
        self.logical_to_physical[a], self.logical_to_physical[b] = v, u
        self.physical_to_logical[u], self.physical_to_logical[v] = b, a
        self.visited[a].add(v)
        self.visited[b].add(u)
        self.swap_history.append((u, v))
        for x in (u, v):
            for y in self.graph.neighbors(x):
                self._record_interaction(self.physical_to_logical[x], self.physical_to_logical[y])

    def swap_physical(self, u, v):
        self.swap(self.physical_to_logical[u], self.physical_to_logical[v])

    def verify_completeness(self):
        required = {tuple(sorted(p)) for p in itertools.combinations(self.graph, 2)}
        missing = sorted(required - self.interacted_pairs)
        return dict(is_complete=not missing, count=len(required & self.interacted_pairs),
                    expected=len(required), missing_pairs=missing)
