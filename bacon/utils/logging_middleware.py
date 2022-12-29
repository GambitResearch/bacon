"""Middleware for logging requests, using Apache combined log format
"""
# Ported from Paste TransLogger class. Original copyright follows.
#
# (c) 2005 Ian Bicking and contributors; written for Paste (http://pythonpaste.org)
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php

import sys
import time
import logging

# allow middleware to work with Django >= 2.0
try:
    from django.utils.deprecation import MiddlewareMixin
except ImportError:
    MiddlewareMixin = object


class LoggingMiddleware(MiddlewareMixin):
    """A middleware logging requests Apache/NCSA Combined Log format.

    This logging middleware will log all requests as they go through.
    They are, by default, sent to a logger named ``'wsgi'`` at the
    INFO level.  Different arguments can be specified using a dict
    as ``LOGGING_MIDDLEWARE_CONF`` config parameter.

    If ``setup_console_handler`` is true, then messages for the named
    logger will be sent to the console.

    The django development server already provides its own logging, so
    the middleware disables itself. If the LoggingMiddleware logs are preferred
    in development too, use disable_on_devel=False.

    The LoggingMiddleware is probably best used as the beginning of the
    ``MIDDLEWARE_CLASSES`` sequence, so that will be invoked on response after
    all the other middleware and will have the possibility to log errors and
    to know exactly the response length.
    """

    format = (
        "%(REMOTE_ADDR)s - %(REMOTE_USER)s [%(time)s] "
        '"%(REQUEST_METHOD)s %(REQUEST_URI)s %(HTTP_VERSION)s" '
        '%(status)s %(bytes)s "%(HTTP_REFERER)s" "%(HTTP_USER_AGENT)s"'
    )

    def __new__(cls, **kwargs):
        # If we have really been invoked as django middleware,
        # check for kw arguments in its configuration instead of
        # expecting them in the constructor.
        if not kwargs:
            try:
                from django.conf import settings

                kwargs = getattr(settings, "LOGGING_MIDDLEWARE_CONF", {})
            except ImportError:
                pass

        rv = super(LoggingMiddleware, cls).__new__(LoggingMiddleware)
        LoggingMiddleware.__init__(rv, **kwargs)
        return rv

    def __init__(
        self,
        logger=None,
        format=None,
        logging_level=logging.INFO,
        logger_name="wsgi",
        setup_console_handler=True,
        set_logger_level=logging.DEBUG,
        disable_on_devel=True,
    ):

        # Because __init__ is called manually by __new__, it is invoked twice:
        # bail out early the second time as we are already configured.
        if self.__dict__:
            return

        if format is not None:
            self.format = format
        self.logging_level = logging_level
        self.logger_name = logger_name
        if logger is None:
            self.logger = logging.getLogger(self.logger_name)
            if setup_console_handler:
                console = logging.StreamHandler()
                console.setLevel(logging.DEBUG)
                # We need to control the exact format:
                console.setFormatter(logging.Formatter("%(message)s"))
                self.logger.addHandler(console)
                self.logger.propagate = False
            if set_logger_level is not None:
                self.logger.setLevel(set_logger_level)
        else:
            self.logger = logger

        # If running under the development server, it will try to log as well
        if "django.core.management.commands.runserver" in sys.modules:
            if disable_on_devel:
                from django.core.exceptions import MiddlewareNotUsed

                raise MiddlewareNotUsed("development server detected")

            else:
                self.logger.info("development server detected: disabling its logs")
                try:
                    from django.core.servers.basehttp import WSGIRequestHandler

                    WSGIRequestHandler.log_message = lambda self, format, *args: None
                except Exception as e:
                    self.logger.warn(
                        "disbling logs failed: %s - %s", e.__class__.__name__, e
                    )

    def process_response(self, request, response):
        environ = request.META

        start = time.localtime()
        req_uri = request.get_full_path()
        method = request.method

        bytes = response.get("Content-Length", None)
        if bytes is None and isinstance(response.content, str):
            bytes = len(response.content)

        status_code = response.status_code

        self.write_log(environ, method, req_uri, start, status_code, bytes)
        return response

    def write_log(self, environ, method, req_uri, start, status_code, bytes):
        if bytes is None:
            bytes = "-"
        if time.daylight:
            offset = time.altzone / 60 / 60 * -100
        else:
            offset = time.timezone / 60 / 60 * -100
        if offset >= 0:
            offset = "+%0.4d" % (offset)
        elif offset < 0:
            offset = "%0.4d" % (offset)
        d = {
            "REMOTE_ADDR": environ.get("REMOTE_ADDR") or "-",
            "REMOTE_USER": environ.get("REMOTE_USER") or "-",
            "REQUEST_METHOD": method,
            "REQUEST_URI": req_uri,
            "HTTP_VERSION": environ.get("SERVER_PROTOCOL"),
            "time": time.strftime("%d/%b/%Y:%H:%M:%S ", start) + offset,
            "status": status_code,
            "bytes": bytes,
            "HTTP_REFERER": environ.get("HTTP_REFERER", "-"),
            "HTTP_USER_AGENT": environ.get("HTTP_USER_AGENT", "-"),
        }
        message = self.format % d
        self.logger.log(self.logging_level, message)
