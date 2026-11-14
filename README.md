# SWAP Networks with k-Dominating Paths

This repository contains the Python and ASP implementation of the constructions in **“SWAP networks with k-dominating paths”** by Riccardo Romanello, Daniele Lizzio Bosco, Giuseppe Serra, and Carla Piazza.

The implementation is deliberately limited to the methods used in the paper: minimum 1- and 2-dominating paths, the four corresponding SWAP-network constructions, and the two simulated-annealing baselines used for comparison. Exploratory algorithms, additional radii, depth experiments, synthetic sweeps, and unrelated proof/benchmark utilities from the development repository are not included.

## Which construction should I use?

For each backbone radius, both the previous construction and the paper's new construction are available:

| Backbone | Previous construction (`old`) | New construction (`new`) | Recommended within that radius |
|---|---|---|---|
| **1-mDP** | **Insertion and Grouping** — Algorithm 2 | **Early Leaves Insertion** — Algorithm 3 | **Early Leaves Insertion** |
| **2-mDP** | **Delayed Insertion** — Section 5.2 | **Vines** — Algorithm 4 | **Vines** |

The default `--method recommended` selects Early Leaves Insertion for radius 1 and Vines for radius 2. The older constructions remain available to reproduce the comparison.

**There is no universally best radius.** The paper's experiments show that the backbone choice depends on the hardware topology:
- On the tested heavy-hex families, 2-mDP constructions are consistently better once the instances are sufficiently large, and Vines is the best of the four deterministic constructions.
- On the tested square grids, 1-mDP constructions are better: the additional cost of inserting the larger off-path set can outweigh the shorter 2-mDP backbone.
- On the IBM coupling maps, 1-mDP performs best on the tested 16–27-qubit devices, while 2-mDP can provide lower SWAP counts on larger devices.

Thus, use `recommended` to select the stronger construction **for a chosen radius**; compare radius 1 and radius 2 when selecting the backbone for a new topology.

## Quick start

Requirements: Python 3.10+, Clingo 5.8.x, and the Python dependencies in `requirements.txt`.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e python
```

Compute a 1-mDP and build the recommended 1-mDP network:

```bash
mdp-sn run \
  --topology ASP/Topologies/127_fake_brisbane.lp \
  --radius 1 \
  --method recommended
```

Compute a 2-mDP and build the recommended 2-mDP network:

```bash
mdp-sn run \
  --topology ASP/Topologies/127_fake_brisbane.lp \
  --radius 2 \
  --method recommended
```

See [USAGE.md](USAGE.md) for the full method selection, outputs, baselines, and direct ASP invocation.

## Repository layout

```text
ASP/
  Solvers/
    minimum_k_dominating_path.lp   # exact minimum r-dominating path encoding
  Topologies/                      # hardware coupling maps used in the experiments

python/mdp_sn/
  algorithms/
    insertion_grouping.py          # Algorithm 2: 1-mDP, previous method
    early_leaves_insertion.py      # Algorithm 3: 1-mDP, new method
    delayed_insertion.py           # Section 5.2: 2-mDP, previous method
    vines.py                       # Algorithm 4: 2-mDP, new method
  baselines/
    simulated_annealing.py         # Python SA baseline
    autoswap.py                    # adapter for the external AutoSwap project
  core.py                          # ASP path search and shared pipeline primitives
  leaf_insertion.py                        # deterministic leaf insertion/grouping
  swap_position.py                 # optimal Swap-and-Position on a line
  verifier.py                      # physical SWAP legality and pair-interaction verifier

tests/
  test_paper_algorithms.py
```

## Method selection

`--radius` chooses the backbone problem:
- `1`: a minimum dominating path (1-mDP);
- `2`: a minimum 2-dominating path (2-mDP).

`--method` chooses the construction:
- `old`: Algorithm 2 for radius 1; Delayed Insertion for radius 2;
- `new`: Early Leaves Insertion for radius 1; Vines for radius 2;
- `recommended` (default): `new` for either radius;
- alternatively, use the exact method names `insertion-grouping`, `early-leaves-insertion`, `delayed-insertion`, or `vines`.

The implementation tries both orientations of the ASP path and keeps the shorter verified network. Every returned schedule is independently replayed on the hardware graph; illegal physical SWAPs or missing pair interactions cause an error instead of being silently accepted.

## Important preconditions and fallbacks

- The ASP encoding searches for a minimum path of the selected radius. If the solver reaches the time limit, the best path found so far is returned with `optimal: false`; check the saved JSON metadata before treating the backbone as proven minimum.
- Early Leaves Insertion applies when the number of off-path vertices is at most the number of path vertices. Otherwise it falls back to Algorithm 2, as described in Section 4.5.
- Vines applies when the number of off-path vertices is at most the number of path vertices. Otherwise it falls back to Delayed Insertion, as described in Section 5.3.
- A topology may admit no path of a requested radius. In that case the command reports `UNSAT` and does not construct a network.

## Baselines

The paper compares against a Python reimplementation of the simulated-annealing method and the authors' AutoSwap implementation. Both are kept as baselines, not as proposed constructions.

The Python SA implementation uses the paper's settings by default: 2,000 annealing steps per layer and a geometric temperature schedule from 10 to 0.01.

AutoSwap is not vendored. The adapter in `python/mdp_sn/baselines/autoswap.py` calls the authors' implementation without modifying it; clone the upstream repository and pass its directory to the command. The adapter physically replays the produced swaps and reports whether the network is complete.

## Reproducibility and scope

`ASP/Topologies/` contains the 22 IBM coupling maps from the paper's device table that were present in the supplied source snapshot. The paper also reports Berlin, Prague, Washington, and Aachen, but their `.lp` topology files were not present in that snapshot, so they are not fabricated here. The synthetic heavy-hex and square-grid instances are likewise not bundled; any connected graph in the documented ASP format can be used as input. The repository does not include precomputed result dumps: run commands write fresh JSON schedules and metadata under `results/` by default.

The ASP encoding computes the backbone only. The SWAP-network construction is performed in Python, as in the paper. The old exact ASP encodings for complete SWAP networks and the later experimental encodings are intentionally excluded.
