#  Copyright 2022 Red Hat, Inc.
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
"""
Django settings.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.1/ref/settings/

Quick-start development settings - unsuitable for production
See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

Common settings:

* SECRET_KEY
* DEBUG
* ALLOWED_HOSTS

Database settings:

* DB_HOST - Database hostname (default: "127.0.0.1")
* DB_PORT - Database port (default: 5432)
* DB_USER - Database username (default: "postgres")
* DB_PASSWORD - Database user password (default: None)
* DB_NAME - Database name (default: "eda")

Redis queue settings:

* MQ_UNIX_SOCKET_PATH - Redis unix socket path, mutually exclusive with
    host and port (default: None)
* MQ_HOST - Redis queue hostname (default: "127.0.0.1")
* MQ_PORT - Redis queue port (default: 6379)
* MQ_DB - Redis queue database (default: 0)
"""
import dynaconf

settings = dynaconf.Dynaconf(envvar_prefix="EDA")

# ---------------------------------------------------------
# DJANGO SETTINGS
# ---------------------------------------------------------

SECRET_KEY = settings.get("SECRET_KEY")

DEBUG = settings.get("DEBUG", False)

ALLOWED_HOSTS = settings.get("ALLOWED_HOSTS", [])


# Application definition
INSTALLED_APPS = [
    "daphne",
    # Django apps
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    # Third party apps
    "rest_framework",
    "drf_spectacular",
    "django_rq",
    "django_filters",
    # Local apps
    "aap_eda.api",
    "aap_eda.core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "aap_eda.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ],
        },
    },
]

WSGI_APPLICATION = "aap_eda.wsgi.application"

ASGI_APPLICATION = "aap_eda.asgi.application"


# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": settings.get("DB_HOST", "127.0.0.1"),
        "PORT": settings.get("DB_PORT", 5432),
        "USER": settings.get("DB_USER", "postgres"),
        "PASSWORD": settings.get("DB_PASSWORD"),
        "NAME": settings.get("DB_NAME", "eda"),
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",  # noqa: E501
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = "static/"

MEDIA_ROOT = settings.get("MEDIA_ROOT", "/var/lib/eda/files")

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "core.User"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "aap_eda.api.pagination.DefaultPagination",  # noqa: E501
    "PAGE_SIZE": 20,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# ---------------------------------------------------------
# TASKING SETTINGS
# ---------------------------------------------------------
RQ = {
    "QUEUE_CLASS": "aap_eda.core.tasking.Queue",
    "JOB_CLASS": "aap_eda.core.tasking.Job",
}

RQ_UNIX_SOCKET_PATH = settings.get("MQ_UNIX_SOCKET_PATH", None)

if RQ_UNIX_SOCKET_PATH:
    RQ_QUEUES = {
        "default": {
            "UNIX_SOCKET_PATH": RQ_UNIX_SOCKET_PATH,
        },
    }
else:
    RQ_QUEUES = {
        "default": {
            "HOST": settings.get("MQ_HOST", "localhost"),
            "PORT": settings.get("MQ_PORT", 6379),
        }
    }
RQ_QUEUES["default"]["DB"] = settings.get("MQ_DB", 0)

# ---------------------------------------------------------
# APPLICATION SETTINGS
# ---------------------------------------------------------

API_PREFIX = settings.get("API_PREFIX", "api/eda").strip("/")

SPECTACULAR_SETTINGS = {
    "TITLE": "Event Driven Ansible API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": f"/{API_PREFIX}/v[0-9]",
    "SCHEMA_PATH_PREFIX_TRIM": True,
    "SERVERS": [{"url": f"/{API_PREFIX}/v1"}],
    "PREPROCESSING_HOOKS": [
        "aap_eda.api.openapi.preprocess_filter_api_routes"
    ],
}

# ---------------------------------------------------------
# LOGGING SETTINGS
# ---------------------------------------------------------

APP_LOG_LEVEL = settings.get("APP_LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{asctime} {levelname:<8} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.channels.server": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "aap_eda": {
            "handlers": ["console"],
            "level": APP_LOG_LEVEL,
            "propagate": False,
        },
    },
}
