import networkx as nx

from mdp_sn.core import replay
from mdp_sn.algorithms.insertion_grouping import run as insertion_grouping
from mdp_sn.algorithms.early_leaves_insertion import early_leaves_insertion
from mdp_sn.algorithms.delayed_insertion import run as delayed_insertion
from mdp_sn.algorithms.vines import vines


def checked(graph, history):
    assert replay(graph, history).verify_completeness()["is_complete"]


def test_paper_line_example_1_mdp():
    graph = nx.path_graph(8)
    path = list(range(1, 7))
    old, _ = insertion_grouping(graph, path)
    new, info = early_leaves_insertion(graph, path)
    assert len(old) == 27
    assert len(new) == 22
    assert info["algorithm"] == "Early Leaves Insertion"
    checked(graph, old)
    checked(graph, new)


def test_paper_line_example_2_mdp():
    graph = nx.path_graph(8)
    path = list(range(2, 6))
    old, _ = delayed_insertion(graph, path)
    new, info = vines(graph, path)
    assert len(old) == 29
    assert len(new) == 21
    assert info["algorithm"] == "Vines"
    checked(graph, old)
    checked(graph, new)


def test_vines_uses_delayed_insertion_when_off_path_set_is_too_large():
    graph = nx.path_graph(5)
    history, info = vines(graph, [2])
    assert info["fallback"] == "Delayed Insertion"
    checked(graph, history)


def test_vines_on_small_two_level_caterpillars():
    # The 2-mDP is the spine; each vine has at most one far leaf.
    for p in range(2, 8):
        graph = nx.path_graph(p)
        next_vertex = p
        for anchor in range(p):
            if anchor % 2 == 0:
                leaf = next_vertex
                next_vertex += 1
                graph.add_edge(anchor, leaf)
                if anchor % 3 == 0:
                    far = next_vertex
                    next_vertex += 1
                    graph.add_edge(leaf, far)
        if next_vertex - p <= p:
            history, _ = vines(graph, list(range(p)))
            checked(graph, history)



def test_early_insertion_falls_back_when_there_are_too_many_leaves():
    graph = nx.star_graph(4)
    history, info = early_leaves_insertion(graph, [0])
    assert info["fallback"] == "Insertion and Grouping"
    checked(graph, history)
