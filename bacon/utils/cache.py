"""Decorators to cache Python values.

The module also handles an invalidation register allowing to call functions
to invalidate a cache upon events triggered from the outside, e.g.::

	dbcache = {}

	@cached_in(dbcache)
	def get_from_database(id):
		# slooooow
		return {'id': id}

	@invalidating('database')
	def clear_cache():
		dbcache.clear()

	# if the database is changed, the following function can be called:
	invalidate('database')
"""

from functools import wraps
from collections import defaultdict

import logging
logger = logging.getLogger('cache')
logger.setLevel(logging.DEBUG)  # TODO: disable after debugging


def cached(f):
	"""Evaluate a function call only once.

	The function should be called using only positional arguments. All the
	parameters should be hashable.

	The decorator is not thread-safe. If needed use the `synchro` decorator
	to serialize access to the function.
	"""
	return cached_in({})(f)


def cached_in(cache):
	"""Evaluate a function call only once.

	Use an external dictionary as cache: this allows interaction with the cache
	from other functions.
	"""
	def cached_in_(f):
		@wraps(f)
		def cached_in__(*args):
			try:
				return cache[args]
			except KeyError:
				cache[args] = f(*args)
				return cache[args]

		return cached_in__
	return cached_in_


def cached_method(f):
	"""Evaluate a method call only once. Results are cached per class instance.

	The method should be called using only positional arguments. All the
	parameters should be hashable.

	The decorator is not thread-safe. If needed use the `synchro_method`
	decorator to serialize access to the function.
	"""
	cache_name = "_cache_%s" % f.__name__

	@wraps(f)
	def cached_method_(self, *args):
		try:
			cache = getattr(self, cache_name)
		except AttributeError:
			cache = {}
			setattr(self, cache_name, cache)

		try:
			return cache[args]
		except KeyError:
			cache[args] = f(self, *args)
			return cache[args]

	return cached_method_


_invalidators = defaultdict(list)


def invalidating(*names):
	"""Decorator to register a function in the invalidation system."""
	def invalidating_(f):
		for name in names:
			_invalidators[name].append(f)
		return f

	return invalidating_


def invalidate(name, *args):
	"""Invalidate all the objects repending on the system *name*.

	Call all the functions decorated with @invalidating(name), pass them *args.
	"""
	logger.debug("invalidating '%s' with args %s", name, args)
	fs = _invalidators.get(name)
	if fs is None:
		logger.warning("no invalidator registered: '%s'", name)
		return

	for f in fs:
		logger.debug("calling %r", f)
		try:
			f(*args)
		except Exception as e:
			logger.error("error calling %r with args %r: %s - %s",
				f, args, e.__class__.__name__, e)
