"""Package containing builders to build query from string representations."""


class QueryBuilder:
    """Builds a query from a string representation.

    The class can also return the string representation of a query from a context.

    This is an abstract class: concrete subclasses implement a specific
    query language.
    """

    def __init__(self, context, cubedef=None):
        """The cubedef is used at parse time: you can avoid specifying it
        in the constructor if not available.
        """
        # what the context is is dictated by subclasses, so I won't store it
        self.cubedef = cubedef

    def parse(self, name, query):
        """Parse a new query from the context."""
        if self.cubedef is None:
            raise ValueError("cube definition not set")

        for cmd, args in self.tokenize(name):
            query = self._add(query, cmd, args)

        return query

    def _add(self, query, cmd, args):
        return getattr(self, cmd)(query, *args)

    def tokenize(self, name):
        raise NotImplementedError

    def to_string(self, query, name):
        raise NotImplementedError

    def get_value(self, control, name=None):
        raise NotImplementedError
