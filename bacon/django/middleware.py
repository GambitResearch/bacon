from django.http import Http404
from django.template import TemplateSyntaxError
from django.conf import settings

from bacon import errors

# allow middleware to work with Django >= 2.0
try:
    from django.utils.deprecation import MiddlewareMixin
except ImportError:
    MiddlewareMixin = object


class ErrorTo404Middleware(MiddlewareMixin):
	"""Middleware to handle application exceptions raised by bacon.

	Let's convert them in 404. Either it is a bug in bacon (but bacon has none)
	or more likely the user is hacking the URL, so a 404 seems appropriate.

	The middleware is probably best used at the end of the ``MIDDLEWARE_CLASSES``
	sequence because it should only intercept errors raised in the view
	function or in the template rendering.
	"""

	def process_exception(self, request, exception):
		# There are no bacon bugs on live, but we need to see bugs
		# while developing to make it that way.
		if settings.DEBUG:
			return

		if isinstance(exception, errors.AppError):
			return self.process_bacon_exception(request, exception)
		elif isinstance(exception, TemplateSyntaxError):
			if hasattr(exception, 'exc_info'):
				exception = exception.exc_info[1]
				if isinstance(exception, errors.AppError):
					return self.process_bacon_exception(request, exception)

	def process_bacon_exception(self, request, exception):
		raise Http404(str(exception))
