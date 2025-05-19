#  Copyright 2025 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import django
from django.core.cache import cache
from django.db import connection

"""This module is an optimization for dispatcherd workers

This sets up Django pre-fork, which must be implemented as a module to run
on-import for compatibility with multiprocessing forkserver.
This should never be imported by other modules, which is why it is called
hazmat.
"""


django.setup()

# connections may or may not be open, but
# before forking, all connections should be closed

cache.close()
connection.close()
