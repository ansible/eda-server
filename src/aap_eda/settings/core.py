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

# Define all settings use internally, not exposed to users for overwriting.

# Defines feature flags, and their conditions.
# See https://cfpb.github.io/django-flags/
ANALYTICS_FEATURE_FLAG_NAME = "FEATURE_EDA_ANALYTICS_ENABLED"

FLAGS = {
    ANALYTICS_FEATURE_FLAG_NAME: [
        {
            "condition": "boolean",
            "value": False,
        },
    ],
}

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
    "django_filters",
    "ansible_base.rbac",
    "ansible_base.resource_registry",
    "ansible_base.jwt_consumer",
    "ansible_base.rest_filters",
    "ansible_base.feature_flags",
    # Local apps
    "aap_eda.api",
    "aap_eda.core",
]


MIDDLEWARE = [
    "aap_eda.middleware.request_log_middleware.RequestLogMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "crum.CurrentRequestUserMiddleware",
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

USE_I18N = True

TIME_ZONE = "UTC"

USE_TZ = True

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "core.User"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "aap_eda.api.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "aap_eda.api.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
        "aap_eda.api.authentication.WebsocketJWTAuthentication",
        "ansible_base.jwt_consumer.eda.auth.EDAJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "ansible_base.rbac.api.permissions.AnsibleBaseObjectPermissions",
    ],
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "DEFAULT_METADATA_CLASS": "aap_eda.api.metadata.EDAMetadata",
    "EXCEPTION_HANDLER": "aap_eda.api.exceptions.api_fallback_handler",
}


# ---------------------------------------------------------
# DISPATCHERD SETTINGS
# ---------------------------------------------------------
DISPATCHERD_QUEUE_HEALTHCHECK_TIMEOUT = 3
DISPATCHERD_DEFAULT_CHANNEL = "default"

DISPATCHERD_STARTUP_TASKS = {
    "aap_eda.tasks.analytics.schedule_gather_analytics": {},
}

DISPATCHERD_SCHEDULE_TASKS = {
    "aap_eda.tasks.orchestrator.monitor_rulebook_processes": {"schedule": 5},
    "aap_eda.tasks.project.monitor_project_tasks": {"schedule": 30},
}


ANSIBLE_BASE_CUSTOM_VIEW_PARENT = "aap_eda.api.views.dab_base.BaseAPIView"

# ---------------------------------------------------------
# DJANGO ANSIBLE BASE RESOURCES REGISTRY SETTINGS
# ---------------------------------------------------------
ANSIBLE_BASE_RESOURCE_CONFIG_MODULE = "aap_eda.api.resource_api"

# ---------------------------------------------------------
# DJANGO ANSIBLE BASE RBAC SETTINGS
# ---------------------------------------------------------
DEFAULT_ORGANIZATION_NAME = "Default"
ANSIBLE_BASE_SERVICE_PREFIX = "eda"
ANSIBLE_BASE_TEAM_MODEL = "core.Team"
ANSIBLE_BASE_ORGANIZATION_MODEL = "core.Organization"

# Organization and object roles will come from create_initial_data
ANSIBLE_BASE_ROLE_PRECREATE = {}

ANSIBLE_BASE_ALLOW_SINGLETON_USER_ROLES = True
ANSIBLE_BASE_CHECK_RELATED_PERMISSIONS = ["view"]

DEFAULT_SYSTEM_PG_NOTIFY_CREDENTIAL_NAME = "_DEFAULT_EDA_PG_NOTIFY_CREDS"
