# flake8: noqa
from .default import *

DEBUG = True

SECRET_KEY = "insecure"

DATABASES["default"]["PASSWORD"] = "secret"
