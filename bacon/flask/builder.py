"""Query builders specialized for Flask interaction"""

from bacon.builders.url import UrlQueryBuilder


class FlaskQueryBuilder(UrlQueryBuilder):
    """Query builder specialized in dealing with Flask requests."""

    def __init__(self, context, cubedef=None, **kwargs):
        # the context here is a Flask request
        if context.method == "GET":
            query_dict = dict(context.args.items())
        else:
            raise NotImplementedError("method %s not supported" % context.method)

        super(FlaskQueryBuilder, self).__init__(query_dict, cubedef=cubedef, **kwargs)
