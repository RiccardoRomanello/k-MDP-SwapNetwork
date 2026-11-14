# Usage

This guide explains how to run the two backbone problems and select either construction associated with each one.

## 1. Install

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e python
```

The ASP backbone solver is exposed by the Python `clingo` package. The command-line `clingo` executable is optional; it is only needed if you want to run the ASP encoding directly.

## 2. Run a 1-mDP construction

A 1-mDP is a minimum dominating path: every vertex is on the path or adjacent to it.

### Previous construction: Insertion and Grouping (Algorithm 2)

```bash
mdp-sn run --topology ASP/Topologies/127_fake_brisbane.lp \
  --radius 1 --method old
```

Equivalent explicit name:

```bash
mdp-sn run --topology ASP/Topologies/127_fake_brisbane.lp \
  --radius 1 --method insertion-grouping
```

### New construction: Early Leaves Insertion (Algorithm 3)

```bash
mdp-sn run --topology ASP/Topologies/127_fake_brisbane.lp \
  --radius 1 --method new
```

Equivalent explicit name:

```bash
mdp-sn run --topology ASP/Topologies/127_fake_brisbane.lp \
  --radius 1 --method early-leaves-insertion
```

**Recommended 1-mDP setting:** `--radius 1 --method new` (Early Leaves Insertion).

Early Leaves Insertion lets a leaf replace a complete path label during Swap-and-Position and follow its remaining moves. The implementation evaluates all possible target blocks and keeps the shortest verified schedule. If there are more leaves than path vertices, it falls back to Algorithm 2, as in Section 4.5.

## 3. Run a 2-mDP construction

A 2-mDP is a minimum path such that every vertex is at graph distance at most two from the path. Vertices outside the path are classified as leaves (distance one) and far leaves (distance two), with each far leaf assigned a parent leaf in the BFS forest.

### Previous construction: Delayed Insertion (Section 5.2)

```bash
mdp-sn run --topology ASP/Topologies/127_fake_brisbane.lp \
  --radius 2 --method old
```

Equivalent explicit name:

```bash
mdp-sn run --topology ASP/Topologies/127_fake_brisbane.lp \
  --radius 2 --method delayed-insertion
```

### New construction: Vines (Algorithm 4)

```bash
mdp-sn run --topology ASP/Topologies/127_fake_brisbane.lp \
  --radius 2 --method new
```

Equivalent explicit name:

```bash
mdp-sn run --topology ASP/Topologies/127_fake_brisbane.lp \
  --radius 2 --method vines
```

**Recommended 2-mDP setting:** `--radius 2 --method new` (Vines).

Vines organizes off-path vertices into a BFS forest rooted at the 2-mDP. Rotations, insertions, and shifts allow labels to climb their vines while Swap-and-Position is running. At the end, the remaining off-path labels are gathered into a block and acquainted. If the off-path set is larger than the backbone, the implementation falls back to Delayed Insertion, as in Section 5.3.

## 4. Recommended defaults and choosing the radius

The default method is `recommended`:

```bash
# Recommended method for a 1-mDP: Early Leaves Insertion
mdp-sn run --topology ASP/Topologies/127_fake_brisbane.lp --radius 1

# Recommended method for a 2-mDP: Vines
mdp-sn run --topology ASP/Topologies/127_fake_brisbane.lp --radius 2
```

This default selects the better construction **within the selected radius**. It does not claim that radius 2 is always better than radius 1.

The paper's experiments indicate:
- heavy-hex: 2-mDP, especially Vines, generally gives the lowest deterministic SWAP counts on the tested larger instances;
- square grids: 1-mDP methods perform better because the insertion cost for the larger off-path set can dominate the shorter 2-mDP backbone;
- IBM coupling maps: 1-mDP performs best on the tested 16–27-qubit devices; 2-mDP can perform better on larger devices.

For an unfamiliar topology, run both radii and compare the verified `swaps` values.

## 5. Solver time limit and output

The ASP path search defaults to 600 seconds. Override it with `--timeout`:

```bash
mdp-sn run --topology ASP/Topologies/127_fake_brisbane.lp \
  --radius 2 --method vines --timeout 1200 \
  --output results/brisbane_2mdp_vines.json
```

If `--output` is omitted, the result is saved under `results/` using the topology, radius, and method in the filename.

The JSON contains:
- `backbone_path`, `backbone_size`, and `asp.status` / `asp.optimal`;
- `radius`, `backbone`, and the selected `method`;
- `swaps` and the complete sequential `schedule` as physical edge pairs;
- `verified`, which is true only after independent replay confirms every pair has become adjacent.

A `TIMEOUT` status can still include a feasible path found before the time limit. In that case `asp.optimal` is false: the generated network is valid for that path, but the path's minimum cardinality has not been proven.

## 6. Run the Python simulated-annealing baseline

The SA baseline defaults to the settings described in Section 6: 2,000 annealing steps per layer, with temperature decreasing geometrically from 10 to 0.01.

```bash
mdp-sn baseline sa \
  --topology ASP/Topologies/127_fake_brisbane.lp \
  --seed 0
```

Change the number of steps or seed if needed:

```bash
mdp-sn baseline sa \
  --topology ASP/Topologies/127_fake_brisbane.lp \
  --steps 2000 --seed 1 \
  --output results/brisbane_sa_seed1.json
```

The resulting layers are replayed on the physical graph. A baseline run is reported as verified only if every pair of logical labels becomes adjacent at least once.

## 7. Run AutoSwap

AutoSwap is an external project and is not copied into this repository. Clone the authors' repository:

```bash
git clone https://github.com/teoparella/AutoSwap.git
```

Then pass the clone directory:

```bash
mdp-sn baseline autoswap \
  --topology ASP/Topologies/127_fake_brisbane.lp \
  --autoswap-dir /path/to/AutoSwap \
  --preset paper --seed 0
```

The adapter uses AutoSwap's published implementation without patching it. `--preset paper` uses the parameter preset defined by the original benchmark adapter; `--preset notebook` is also available. The output is replayed as physical SWAPs, and the JSON reports any missing pair interactions and labeling restarts.

## 8. Run the ASP encoding directly

To inspect the minimum 1-dominating path:

```bash
python -m clingo ASP/Solvers/minimum_k_dominating_path.lp \
  ASP/Topologies/127_fake_brisbane.lp
```

For radius two:

```bash
python -m clingo ASP/Solvers/minimum_k_dominating_path.lp \
  ASP/Topologies/127_fake_brisbane.lp -c radius=2
```

The encoding minimizes the number of vertices in a simple path and requires every graph vertex to be within the selected radius.

## 9. Tests

Run the paper-algorithm regression tests:

```bash
PYTHONPATH=python python -m pytest -q
```

The line example in the paper is used as a regression check:
- 1-mDP: 27 SWAPs for Insertion and Grouping, 22 for Early Leaves Insertion;
- 2-mDP: 29 SWAPs for Delayed Insertion, 21 for Vines.

Each result is replayed by the physical verifier.


## 10. Custom topologies and bundled instances

A topology file is an ASP fact file with a vertex count and undirected edge facts:

```prolog
#const n=5.
edge(0,1).
edge(1,2).
edge(2,3).
edge(3,4).
```

The graph must be connected and use vertex labels `0,...,n-1`. Pass the file through `--topology`; no code changes are required.

The bundle contains 22 IBM coupling maps from the paper's device table that were present in the supplied repository snapshot. Berlin, Prague, Washington, and Aachen are reported in the paper but their topology files were absent from the supplied snapshot. The synthetic heavy-hex and square-grid instances from the paper are not bundled.
