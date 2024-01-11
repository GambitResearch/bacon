"""Query builders specialized for Django interaction"""

from bacon.builders.url import UrlQueryBuilder


class DjangoQueryBuilder(UrlQueryBuilder):
    """Query builder specialized in dealing with Django requests."""

    def __init__(self, context, cubedef=None, **kwargs):
        # the context here is a Django request
        query_dict = context.GET if context.method == "GET" else context.POST
        query_dict = query_dict.copy()  # make it modifiable
        super().__init__(query_dict, cubedef=cubedef, **kwargs)
