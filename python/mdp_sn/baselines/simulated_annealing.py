import networkx as nx
import random
import math
import copy

def generate_swap_network_sa(connectivity_graph: nx.Graph, sa_steps=2000, t_max=10.0, t_min=0.01):
    """
    Replicates the Algorithm using Simulated Annealing
    
    Args:
        connectivity_graph: The hardware graph.
        sa_steps: Number of annealing steps per layer.
        t_max, t_min: Temperature schedule parameters.
    """
    physical_qubits = list(connectivity_graph.nodes())
    n_qubits = len(physical_qubits)
    
    # Mapping: logical_qubit -> physical_qubit
    current_mapping = {q: q for q in physical_qubits}
    
    # Track interacting pairs
    interacted_pairs = set()
    _record_interactions(connectivity_graph, current_mapping, interacted_pairs)
    
    all_pairs_count = n_qubits * (n_qubits - 1) // 2
    layers = []
    
    # Pre-compute all-pairs shortest paths on hardware for fast H calculation
    dist_matrix = dict(nx.all_pairs_shortest_path_length(connectivity_graph))
    
    print(f"Starting Simulated Annealing Optimization for {n_qubits} qubits...")

    while len(interacted_pairs) < all_pairs_count:
        
        # Identify all logical pairs that still need to meet
        unmet_pairs = []
        logical_qubits = list(current_mapping.keys())
        for i in range(len(logical_qubits)):
            for j in range(i + 1, len(logical_qubits)):
                l1, l2 = logical_qubits[i], logical_qubits[j]
                pair = frozenset((l1, l2))
                if pair not in interacted_pairs:
                    unmet_pairs.append((l1, l2))
        
        if not unmet_pairs:
            break

        # --- Simulated Annealing to find best Matching for this Layer ---
        best_matching_for_layer = _run_simulated_annealing(
            connectivity_graph,
            current_mapping,
            unmet_pairs,
            dist_matrix,
            steps=sa_steps,
            t_max=t_max,
            t_min=t_min
        )
        
        layers.append(best_matching_for_layer)
        
        # Update mapping based on the swaps
        for u, v in best_matching_for_layer:
            # Find logical qubits at u and v
            l1 = _get_logical_at(current_mapping, u)
            l2 = _get_logical_at(current_mapping, v)
            # Swap them
            current_mapping[l1] = v
            current_mapping[l2] = u
            
        # Record new interactions
        new_count = _record_interactions(connectivity_graph, current_mapping, interacted_pairs)
        
        # Calculate current "Global Energy" H (Sum of distances of unmet pairs)
        current_H = _calculate_H(current_mapping, unmet_pairs, dist_matrix)
        
        print(f"Layer {len(layers)}: Selected {len(best_matching_for_layer)} swaps via SA. "
              f"Interactions: {len(interacted_pairs)}/{all_pairs_count}. Remaining Cost H: {current_H}")

    return layers

def _run_simulated_annealing(graph, mapping, unmet_pairs, dist_matrix, steps, t_max, t_min):
    """
    Section III.G: Uses SA to optimize the set of swaps (matching) for the current layer.
    Minimizes H = Sum of distances of unmet pairs AFTER the candidate swaps.
    """
    edges = list(graph.edges())
    
    # Initial State: Empty matching (no swaps)
    current_matching = [] 
    
    # Calculate Initial H (Energy)
    current_H = _calculate_H_candidate(mapping, current_matching, unmet_pairs, dist_matrix)
    
    best_matching = list(current_matching)
    best_H = current_H
    
    for step in range(steps):
        frac = step / steps
        T = t_max * (t_min / t_max) ** frac
        
        # --- Generate Candidate (Perturbation) ---
        # We modify the current matching slightly to create a candidate matching.
        # Operations: Add a valid edge, Remove an edge, or Swap an edge?
        candidate_matching = list(current_matching)
        
        # Randomly decide to ADD or REMOVE/SWAP
        action = random.choice(['add', 'remove'])
        
        if action == 'add':
            # Try to add a random edge from the graph that doesn't conflict
            # Shuffle edges to pick a random one
            random_edge = random.choice(edges)
            if _is_valid_addition(candidate_matching, random_edge):
                candidate_matching.append(random_edge)
        
        elif action == 'remove' and len(candidate_matching) > 0:
            # Remove a random edge from the current matching
            idx = random.randrange(len(candidate_matching))
            candidate_matching.pop(idx)
            
       
        H_candidate = _calculate_H_candidate(mapping, candidate_matching, unmet_pairs, dist_matrix)
        
        delta_H = H_candidate - current_H
        
        
        if delta_H < 0 or random.random() < math.exp(-delta_H / T):
            
            current_matching = candidate_matching
            current_H = H_candidate
            
            if current_H < best_H:
                best_H = current_H
                best_matching = list(current_matching)
                
    return best_matching

def _calculate_H(mapping, unmet_pairs, dist_matrix):
    """
    Calculates the 'Hamiltonian' H: Sum of distances between all unmet logical pairs
    given the current mapping.
    """
    H = 0
    for l1, l2 in unmet_pairs:
        p1 = mapping[l1]
        p2 = mapping[l2]
        H += dist_matrix[p1][p2]
    return H

def _calculate_H_candidate(base_mapping, candidate_matching, unmet_pairs, dist_matrix):
    """
    Calculates H_candidate: The cost H that would result IF we applied the candidate_matching.
    Does NOT modify the base_mapping.
    """
    # We only need to track changes for the qubits involved in the matching
    
    swap_map = {} 
    for u, v in candidate_matching:
        swap_map[u] = v
        swap_map[v] = u
        
    H = 0
    for l1, l2 in unmet_pairs:
        p1_current = base_mapping[l1]
        p2_current = base_mapping[l2]
        
        # Apply swap if applicable
        p1_next = swap_map.get(p1_current, p1_current)
        p2_next = swap_map.get(p2_current, p2_current)
        
        # Distance in the new configuration
        H += dist_matrix[p1_next][p2_next]
        
        if dist_matrix[p1_next][p2_next] == 1:
            H -= 5 # Bonus weight for immediate adjacency
            
    return H

def _is_valid_addition(matching, new_edge):
    """Checks if adding new_edge (u, v) keeps the matching valid (disjoint)."""
    u, v = new_edge
    for mu, mv in matching:
        if u == mu or u == mv or v == mu or v == mv:
            return False
    return True

def _get_logical_at(mapping, phys_node):
    for l, p in mapping.items():
        if p == phys_node:
            return l
    return None

def _record_interactions(graph, mapping, interacted_pairs):
    count = 0
    for u, v in graph.edges():
        l1 = _get_logical_at(mapping, u)
        l2 = _get_logical_at(mapping, v)
        if l1 is not None and l2 is not None:
            pair = frozenset((l1, l2))
            if pair not in interacted_pairs:
                interacted_pairs.add(pair)
                count += 1
    return count

# --- Execution Example ---
if __name__ == "__main__":
    G = nx.Graph()
    G.add_edges_from([(1, 0), (1, 2), (3, 2), (4, 3), (4, 15), (5, 4), (6, 5), (7, 6), (8, 7), (8, 9), (10, 9), (10, 11), (11, 12), (12, 13), (14, 0), (14, 18), (16, 8), (17, 12), (17, 30), (18, 19), (19, 20), (20, 33), (21, 20), (21, 22), (22, 15), (23, 22), (23, 24), (25, 24), (26, 16), (26, 25), (26, 27), (28, 27), (29, 28), (29, 30), (31, 30), (31, 32), (32, 36), (33, 39), (34, 24), (35, 28), (35, 47), (36, 51), (37, 38), (38, 39), (40, 39), (41, 40), (41, 53), (42, 41), (43, 34), (43, 42), (43, 44), (45, 44), (45, 46), (47, 46), (47, 48), (49, 48), (49, 50), (50, 51), (52, 37), (53, 60), (54, 45), (55, 49), (56, 52), (56, 57), (57, 58), (59, 58), (59, 60), (61, 60), (61, 62), (63, 62), (63, 64), (64, 54), (64, 65), (66, 65), (67, 66), (68, 55), (68, 67), (69, 68), (69, 70), (71, 58), (71, 77), (72, 62), (73, 66), (73, 85), (74, 70), (75, 76), (77, 76), (78, 77), (78, 79), (79, 91), (80, 79), (80, 81), (81, 72), (81, 82), (82, 83), (84, 83), (85, 84), (86, 85), (86, 87), (87, 88), (89, 74), (89, 88), (90, 75), (90, 94), (92, 83), (92, 102), (93, 87), (93, 106), (95, 94), (95, 96), (97, 96), (97, 98), (98, 91), (99, 98), (99, 100), (101, 100), (101, 102), (102, 103), (104, 103), (105, 104), (106, 105), (107, 106), (107, 108), (109, 96), (110, 100), (110, 118), (111, 104), (112, 108), (112, 126), (113, 114), (114, 109), (114, 115), (116, 115), (117, 116), (117, 118), (119, 118), (119, 120), (120, 121), (121, 122), (122, 111), (123, 122), (124, 123), (125, 124), (126, 125)])
    
    swap_layers = generate_swap_network_sa(G, sa_steps=2000)
    
    print("\nFinal Swap Network:")
    l = 0
    for i, layer in enumerate(swap_layers):
        print(f"Layer {i+1}: {layer}")
        l += len(layer)

    print(f"\nSwap network length: {l}")