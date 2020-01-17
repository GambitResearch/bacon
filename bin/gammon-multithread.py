#!/usr/bin/env python
"""Run gammon as a multithread server.

Requires CherryPy server, that can be obtained through::

	wget http://svn.cherrypy.org/trunk/cherrypy/wsgiserver/__init__.py -O wsgiserver.py

"""

import os

try:
	# ~gammon/lib.maggie
	import wsgiserver
except ImportError:
	# wsgiserver module is usually here:
	from cherrypy import wsgiserver
import django.core.handlers.wsgi

import logging
logger = logging.getLogger("gammon")


def parse_options():
	from optparse import OptionParser
	parser = OptionParser()
	parser.add_option("--host", default="localhost",
		help="host to listen to [default: %default]")
	parser.add_option("--port", type='int', default=8000,
		help="port to listen to [default: %default]")
	parser.add_option("--num-threads", metavar="N", type='int', default=20,
		help="number of listening threads [default: %default]")

	opt, args = parser.parse_args()
	if args:
		parser.error("no argument expected, only params")

	return opt

if __name__ == "__main__":
	opt = parse_options()

	os.environ['DJANGO_SETTINGS_MODULE'] = 'gammon.settings'
	server = wsgiserver.CherryPyWSGIServer(
		(opt.host, opt.port),
		django.core.handlers.wsgi.WSGIHandler(),
		server_name='reports.example.com',
		numthreads=opt.num_threads,
	)
	logger.info("listening on %s:%s", opt.host, opt.port)
	try:
		server.start()
	except KeyboardInterrupt:
		server.stop()
