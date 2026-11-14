# ASP: minimum k-dominating paths

The paper uses ASP only to compute the minimum 1- and 2-dominating path that serves as the backbone of the Python construction.

- `Solvers/minimum_k_dominating_path.lp` is the encoding used by the runner.
- `Solvers/portfolio_bb_usc.txt` configures Clingo's two-thread portfolio: branch-and-bound and core-guided optimization.
- `Topologies/` contains the graph instances in ASP fact format.

The runner invokes Clingo with `radius=1` or `radius=2`, a two-thread portfolio, and a default time limit of 600 seconds. The solver minimizes the number of vertices in the path. If the time limit is reached, the best incumbent is retained and the output records that optimality was not proven.

Direct invocation from the repository root:

```bash
python -m clingo ASP/Solvers/minimum_k_dominating_path.lp \
  ASP/Topologies/127_fake_brisbane.lp -c radius=1 -t 2 \
  --configuration=ASP/Solvers/portfolio_bb_usc.txt
```

Use `-c radius=2` for a 2-mDP. The graph must be connected and its vertices must be labelled `0,...,n-1`.

The exact SWAP schedule is not synthesized in ASP: all four constructions in the paper are implemented in Python.
