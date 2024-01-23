"""Some utility functions to deal with graphs."""
from networkx import DiGraph

def ancestors(graph: DiGraph, node):
    """Return the set of ancestors in a `DiGraph`

    Ancestors are nodes having a path from them to *node*.
    """
    acc = set()

    def _ancestors(n):
        for s in graph.predecessors(n):
            if s not in acc:
                acc.add(s)
                _ancestors(s)

        return acc

    return _ancestors(node)


def descendants(graph: DiGraph, node):
    """Return the set of descendants in a `DiGraph`

    Descendants are nodes having a path from *node* to them.
    """
    acc = set()

    def _descendants(n):
        for s in graph.successors(n):
            if s not in acc:
                acc.add(s)
                _descendants(s)

        return acc

    return _descendants(node)
