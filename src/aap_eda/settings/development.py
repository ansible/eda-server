# flake8: noqa
import os

os.environ.setdefault("EDA_DEBUG", "true")
os.environ.setdefault("EDA_SECRET_KEY", "insecure")
os.environ.setdefault("EDA_DB_PASSWORD", "secret")
os.environ.setdefault("EDA_DB_HOST", "localhost")
os.environ.setdefault("EDA_MQ_HOST", "localhost")

from .default import *
