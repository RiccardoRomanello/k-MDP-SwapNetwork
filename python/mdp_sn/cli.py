"""Command-line interface for SWAP networks with k-dominating paths."""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from .core import load_graph, replay, solve_path


def _resolve_method(radius, method):
    from .algorithms import insertion_grouping, early_leaves_insertion
    from .algorithms import delayed_insertion, vines

    key = method.lower().replace("_", "-")
    if key == "recommended":
        key = "early-leaves-insertion" if radius == 1 else "vines"
    if key == "old":
        key = "insertion-grouping" if radius == 1 else "delayed-insertion"
    if key == "new":
        key = "early-leaves-insertion" if radius == 1 else "vines"

    choices = {
        1: {
            "insertion-grouping": insertion_grouping.run,
            "early-leaves-insertion": early_leaves_insertion.early_leaves_insertion,
        },
        2: {
            "delayed-insertion": delayed_insertion.run,
            "vines": vines.vines,
        },
    }
    if key not in choices[radius]:
        raise ValueError(
            f"Method '{method}' is not available for radius {radius}. "
            f"Choose old, new, recommended, or one of: {', '.join(choices[radius])}."
        )
    return key, choices[radius][key]


def run_paper_method(args):
    graph = load_graph(args.topology)
    backbone = solve_path(graph, radius=args.radius, seconds=args.timeout)
    if "path" not in backbone:
        print(f"ASP did not return a feasible radius-{args.radius} path: {backbone['status']}")
        return 2

    method_name, algorithm = _resolve_method(args.radius, args.method)
    candidates = []
    for path in (backbone["path"], list(reversed(backbone["path"]))):
        history, info = algorithm(graph, path)
        check = replay(graph, history).verify_completeness()
        if not check["is_complete"]:
            raise RuntimeError(
                f"{method_name} failed verification; missing pairs: {check['missing_pairs'][:10]}"
            )
        candidates.append((len(history), path, history, info))

    _, path, history, info = min(candidates, key=lambda item: (item[0], item[1]))
    result = {
        "topology": Path(args.topology).stem,
        "vertices": len(graph),
        "edges": graph.number_of_edges(),
        "radius": args.radius,
        "backbone": "1-mDP" if args.radius == 1 else "2-mDP",
        "backbone_path": path,
        "backbone_size": len(path),
        "method": method_name,
        "recommended_setting": method_name == ("early-leaves-insertion" if args.radius == 1 else "vines"),
        "asp": {k: v for k, v in backbone.items() if k != "path"},
        "swaps": len(history),
        "verified": True,
        "details": info,
        "schedule": [list(edge) for edge in history],
    }
    output = Path(args.output) if args.output else (
        Path("results") / f"{result['topology']}_r{args.radius}_{method_name}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    print(
        f"{result['topology']}: {result['backbone']} / {method_name}: "
        f"{result['swaps']} SWAPs; verified. Saved to {output}"
    )
    return 0


def run_sa(args):
    from .baselines.simulated_annealing import generate_swap_network_sa

    graph = load_graph(args.topology)
    random.seed(args.seed)
    layers = generate_swap_network_sa(
        graph, sa_steps=args.steps, t_max=10.0, t_min=0.01
    )
    history = [tuple(edge) for layer in layers for edge in layer]
    verification = replay(graph, history).verify_completeness()
    result = {
        "topology": Path(args.topology).stem,
        "baseline": "Simulated Annealing (paper reimplementation)",
        "seed": args.seed,
        "steps_per_layer": args.steps,
        "temperature": {"initial": 10.0, "final": 0.01, "schedule": "geometric"},
        "swaps": len(history),
        "layers": len(layers),
        "verified": verification["is_complete"],
        "missing_pairs": verification["missing_pairs"],
        "schedule": [[list(edge) for edge in layer] for layer in layers],
    }
    output = Path(args.output) if args.output else (
        Path("results") / f"{result['topology']}_sa_seed{args.seed}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    print(f"SA: {len(history)} SWAPs, {len(layers)} layers, "
          f"{'verified' if result['verified'] else 'INCOMPLETE'}; saved to {output}")
    return 0 if result["verified"] else 3


def run_autoswap(args):
    from .baselines.autoswap import run

    graph = load_graph(args.topology)
    history, info = run(
        graph, args.autoswap_dir, seed=args.seed, preset=args.preset,
        iterations=args.iterations,
    )
    result = {
        "topology": Path(args.topology).stem,
        "baseline": "AutoSwap",
        **info,
        "schedule": [list(edge) for edge in history],
    }
    output = Path(args.output) if args.output else (
        Path("results") / f"{result['topology']}_autoswap_seed{args.seed}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    print(f"AutoSwap: {len(history)} SWAPs, "
          f"{'verified' if info['complete'] else 'INCOMPLETE'}; saved to {output}")
    return 0 if info["complete"] else 3


def build_parser():
    parser = argparse.ArgumentParser(
        prog="mdp-sn",
        description="Construct and verify circuit-agnostic SWAP networks from 1- and 2-mDPs.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="compute a minimum path and build a paper construction")
    run.add_argument("--topology", required=True, help="ASP topology file (.lp)")
    run.add_argument("--radius", type=int, choices=(1, 2), required=True)
    run.add_argument(
        "--method", default="recommended",
        help="old, new, recommended, or the paper method name (default: recommended)",
    )
    run.add_argument("--timeout", type=float, default=600, help="ASP time limit in seconds")
    run.add_argument("--output", help="JSON output path")
    run.set_defaults(func=run_paper_method)

    baseline = sub.add_parser("baseline", help="run a simulated-annealing baseline")
    base_sub = baseline.add_subparsers(dest="baseline", required=True)

    sa = base_sub.add_parser("sa", help="run the paper's Python SA reimplementation")
    sa.add_argument("--topology", required=True)
    sa.add_argument("--steps", type=int, default=2000, help="annealing steps per layer (paper: 2000)")
    sa.add_argument("--seed", type=int, default=0)
    sa.add_argument("--output")
    sa.set_defaults(func=run_sa)

    autoswap = base_sub.add_parser("autoswap", help="run the authors' external AutoSwap implementation")
    autoswap.add_argument("--topology", required=True)
    autoswap.add_argument("--autoswap-dir", required=True, help="path to cloned AutoSwap repository")
    autoswap.add_argument("--preset", choices=("paper", "notebook"), default="paper")
    autoswap.add_argument("--iterations", type=int, default=100000)
    autoswap.add_argument("--seed", type=int, default=0)
    autoswap.add_argument("--output")
    autoswap.set_defaults(func=run_autoswap)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
