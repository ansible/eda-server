import logging
import functools
import sys
import os

logger = logging.getLogger('eda.main.utils')

__all__ = [
    'get_search_fields',
    'is_testing'
]

def get_search_fields(model):
    fields = []
    for field in model._meta.fields:
        if field.name in ('username', 'first_name', 'last_name', 'email', 'name', 'description'):
            fields.append(field.name)
    return fields

@functools.cache
def is_testing(argv=None):
    '''Return True if running django or py.test unit tests.'''
    if os.environ.get('DJANGO_SETTINGS_MODULE') == 'eda.main.tests.settings_for_test':
        return True
    argv = sys.argv if argv is None else argv
    if len(argv) >= 1 and ('py.test' in argv[0] or 'py/test.py' in argv[0]):
        return True
    elif len(argv) >= 2 and argv[1] == 'test':
        return True
    return False