Implement `topological_sort(dependencies)` in `toposort.py`.
`dependencies` is a dict like `{'b': ['a'], 'c': ['a', 'b']}` mapping each
node to the list of nodes it depends on. Return a list containing every
node exactly once, such that each node appears after all of its
dependencies. Raise `ValueError` if the graph has a cycle. Nodes with no
entry on the left but referenced as a dependency should still appear in
the output.
