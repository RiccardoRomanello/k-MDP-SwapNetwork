"""Physical leaf insertion, optimal fixed-anchor transport, residual sweep.
P is a mutable list of logical labels. spine is the immutable physical path.
"""
class LeafInsertion:
    def __init__(self, graph, P, verifier):
        self.graph, self.P, self.verifier = graph, P, verifier
        self.spine = tuple(verifier.logical_to_physical[x] for x in P)
        if not self.spine or len(set(self.spine)) != len(self.spine):
            raise ValueError('Expected a nonempty simple path')
        if any(not graph.has_edge(a,b) for a,b in zip(self.spine,self.spine[1:])):
            raise ValueError('Non-edge in physical path')
        self.leaves_per_node = [set() for _ in P]
        for v in sorted(set(graph) - set(self.spine)):
            choices = [i for i,u in enumerate(self.spine) if graph.has_edge(v,u)]
            if not choices:
                raise ValueError('The original pipeline requires distance-1 domination')
            # Initial deterministic anchor; the local refinement below can move a leaf to an unused adjacent anchor.
            self.leaves_per_node[choices[0]].add(v)
        self._remove_triangular_dependencies()
        self.H = [len(s) for s in self.leaves_per_node]
        self.leaves_count = sum(self.H)
        self.swap = 0

    def _remove_triangular_dependencies(self):
        for i, leaves in enumerate(self.leaves_per_node):
            for leaf in sorted(leaves.copy()):
                if len(leaves) < 2:
                    break
                for j, u in enumerate(self.spine):
                    if j != i and not self.leaves_per_node[j] and self.graph.has_edge(leaf,u):
                        leaves.remove(leaf)
                        self.leaves_per_node[j].add(leaf)
                        break

    @staticmethod
    def _plan(H):
        if not H or any(not isinstance(x,int) or x < 0 for x in H):
            raise ValueError('Expected a nonempty nonnegative integer histogram')
        L, N = len(H), min(sum(H), len(H))
        X = [i for i,c in enumerate(H) for _ in range(c)]
        if N == 0:
            return [], 0, 0
        if len(X) <= L:
            # X[i]-i is not sorted when anchors repeat!
            Y = sorted(x-i for i,x in enumerate(X))
            start = max(0, min(Y[(N-1)//2], L-N))
            selected = X
        else:
            # Choose an optimal subset, rather than blindly taking the leftmost L.
            # State: minimum cost selecting j items among the first t sources.
            dp = [(0, ())] + [(float('inf'), ()) for _ in range(N)]
            for x in X:
                for j in range(N,0,-1):
                    candidate = (dp[j-1][0] + abs(x-(j-1)), dp[j-1][1]+(x,))
                    if candidate < dp[j]:
                        dp[j] = candidate
            selected, start = list(dp[N][1]), 0
        cost = sum(abs(x-(start+i)) for i,x in enumerate(selected))
        return selected, start, cost

    def _sync(self):
        self.P[:] = [self.verifier.physical_to_logical[v] for v in self.spine]

    def insert_and_group_leaves(self):
        selected, start, cost = self._plan(self.H)
        available = [sorted(s) for s in self.leaves_per_node]
        assignments = [(x, start+i, available[x].pop(0)) for i,x in enumerate(selected)]
        # Move left-going tokens leftmost first; right-going tokens rightmost first.
        # Targets of already placed tokens are never crossed.
        order = sorted((a for a in assignments if a[1] < a[0]), key=lambda a:a[1])
        order += sorted((a for a in assignments if a[1] > a[0]), key=lambda a:-a[1])
        order += [a for a in assignments if a[1] == a[0]]
        before = len(self.verifier.swap_history)
        for source, target, leaf in order:
            self.verifier.swap_physical(leaf, self.spine[source])
            direction = 1 if target > source else -1
            for j in range(source,target,direction):
                self.verifier.swap_physical(self.spine[j],self.spine[j+direction])
            self.leaves_per_node[source].remove(leaf)
            self.H[source] -= 1
        self.leaves_count -= len(selected)
        self.swap = len(self.verifier.swap_history)-before
        assert self.swap == cost + len(selected)
        self._sync()
        return self.swap, self.P, len(selected), start

    def full_walkthrough(self):
        source = next((i for i,h in enumerate(self.H) if h), None)
        if source is None:
            return 0
        leaf = min(self.leaves_per_node[source])
        before = len(self.verifier.swap_history)
        self.verifier.swap_physical(leaf, self.spine[source])
        # A full sweep meets residents AND labels at still occupied off-path sites.
        last = len(self.spine)-1
        ends = (0,last) if source <= last-source else (last,0)
        pos = source
        for target in ends:
            direction = 1 if target > pos else -1
            for j in range(pos,target,direction):
                self.verifier.swap_physical(self.spine[j],self.spine[j+direction])
            pos = target
        self.H[source] -= 1  # source, not the final position of the moving token
        self.leaves_per_node[source].remove(leaf)
        self.leaves_count -= 1
        self._sync()
        return len(self.verifier.swap_history)-before

    def full_walkthrough_remaining(self):
        total = 0
        while self.leaves_count:
            total += self.full_walkthrough()
        return total
