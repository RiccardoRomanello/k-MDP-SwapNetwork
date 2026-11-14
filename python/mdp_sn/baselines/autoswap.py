"""Thin adapter for the authors' unmodified AutoSwap implementation.

AutoSwap itself is not vendored. Clone https://github.com/teoparella/AutoSwap
and pass its directory with --autoswap-dir.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

PRESETS = {
    "paper": dict(Niter=1000, Annealings_Per_Step=100, Temperature=1,
                  Niter_ZeroTemp=100),
    "notebook": dict(Niter=200, Annealings_Per_Step=10, Temperature=10,
                     Niter_ZeroTemp=20),
}


def run(graph, autoswap_dir, seed=0, preset="paper", iterations=100000):
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("NumPy is required by AutoSwap.") from exc
    directory = str(Path(autoswap_dir).resolve())
    if directory not in sys.path:
        sys.path.insert(0, directory)
    try:
        import SwapNetworkOptimization as sno
    except ImportError as exc:
        raise RuntimeError(
            "Cannot import SwapNetworkOptimization.py. Check --autoswap-dir points "
            "to the cloned AutoSwap repository."
        ) from exc

    from ..verifier import SwapNetworkVerifier

    if preset not in PRESETS:
        raise ValueError(f"Unknown AutoSwap preset: {preset}")
    params = dict(PRESETS[preset])
    random.seed(seed)
    np.random.seed(seed)
    costs, _, annealers, _, labelings = sno.NN_FullOptimization_Kswaps(
        graph=graph,
        Iterations=iterations,
        Niter=params["Niter"],
        Annealings_Per_Step=params["Annealings_Per_Step"],
        Temperature=params["Temperature"],
        Niter_ZeroTemp=params["Niter_ZeroTemp"],
        prob_remove_Swap=0.3,
        Verbose=True,
        PlotVerbose=False,
        Kswaps=1,
        ExponentCost=1,
    )

    verifier = SwapNetworkVerifier(graph)
    believed = list(range(len(graph)))
    restarts = 0
    history = []
    layers = 0
    for index, annealer in enumerate(annealers):
        if list(labelings[index]) != believed:
            restarts += 1
            believed = list(labelings[index])
        for layer in annealer.best_swap:
            if not layer:
                continue
            layers += 1
            positions = {label: position for position, label in enumerate(believed)}
            for a, b in layer:
                u, v = positions[a], positions[b]
                if not graph.has_edge(u, v):
                    raise RuntimeError(f"AutoSwap proposed a non-edge SWAP: {(u, v)}")
                verifier.swap_physical(u, v)
                believed[u], believed[v] = believed[v], believed[u]
                history.append((u, v))
    completeness = verifier.verify_completeness()
    return history, {
        "algorithm": "AutoSwap (authors' implementation, unmodified)",
        "seed": seed,
        "preset": preset,
        "parameters": params,
        "iterations": len(annealers),
        "layers": layers,
        "labeling_restarts": restarts,
        "final_cost": int(costs[-1]) if len(costs) else None,
        "complete": completeness["is_complete"],
        "missing_pairs": completeness["missing_pairs"],
        "swaps": len(history),
    }
