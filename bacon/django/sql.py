from django.db import connection
from django.db import connections

from bacon.sql import BaseConnectionFactory


class DjangoConnectionFactory(BaseConnectionFactory):
    """A factory to be used in django websites to get connections out of Django"""

    def __init__(self, db_name=None):
        self.db_name = db_name
        super(DjangoConnectionFactory, self).__init__()

    def getconn(self):
        if self.db_name is None:
            return connection.connection
        else:
            return connections[self.db_name].connection

    def putconn(self, conn):
        pass
