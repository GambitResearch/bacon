#!/usr/bin/env python


class AppError(Exception):
    """An error defined by the application."""


class QueryError(AppError):
    """Some problem in the query definition."""


class DataError(AppError):
    """Some problem in the data definition."""
