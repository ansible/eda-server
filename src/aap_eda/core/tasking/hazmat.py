import django
from django.core.cache import cache
from django.db import connection

"""This module is an optimization for dispatcherd workers

This sets up Django pre-fork, which must be implemented as a module to run on-import
for compatibility with multiprocessing forkserver.
This should never be imported by other modules, which is why it is called hazmat.
"""


django.setup()

# connections may or may not be open, but
# before forking, all connections should be closed

cache.close()
connection.close()
