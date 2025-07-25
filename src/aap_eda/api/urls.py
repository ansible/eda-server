#  Copyright 2023 Red Hat, Inc.
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
from ansible_base.lib.dynamic_config.dynamic_urls import (
    api_version_urls as dab_urls,
)
from ansible_base.resource_registry.urls import (
    urlpatterns as resource_api_urls,
)
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularJSONAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
    SpectacularYAMLAPIView,
)
from rest_framework import routers

from aap_eda.core import views as core_views

from . import views

router = routers.SimpleRouter()
# basename has to be set when queryset is user-dependent
# which is any model with permissions
router.register("projects", views.ProjectViewSet)
router.register("rulebooks", views.RulebookViewSet)
router.register("activations", views.ActivationViewSet)
router.register(
    "activation-instances",
    views.ActivationInstanceViewSet,
    basename="activationinstance",
)
router.register("audit-rules", views.AuditRuleViewSet)
router.register("users", views.UserViewSet)
router.register(
    "users/me/awx-tokens",
    views.CurrentUserAwxTokenViewSet,
    basename="controller-token",
)
router.register("credential-types", views.CredentialTypeViewSet)
router.register("eda-credentials", views.EdaCredentialViewSet)
router.register("credential-input-sources", views.CredentialInputSourceViewSet)
router.register("decision-environments", views.DecisionEnvironmentViewSet)
router.register("organizations", views.OrganizationViewSet)
router.register("teams", views.TeamViewSet)
router.register("event-streams", views.EventStreamViewSet)
router.register(
    "external_event_stream",
    views.ExternalEventStreamViewSet,
    basename="external_event_stream",
)

openapi_urls = [
    path(
        "openapi.json",
        SpectacularJSONAPIView.as_view(),
        name="openapi-json",
    ),
    path(
        "openapi.yaml",
        SpectacularYAMLAPIView.as_view(),
        name="openapi-yaml",
    ),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(url_name="openapi-json"),
        name="openapi-docs",
    ),
    path(
        "redoc/",
        SpectacularRedocView.as_view(url_name="openapi-json"),
        name="openapi-redoc",
    ),
]

eda_v1_urls = [
    path("config/", views.ConfigView.as_view(), name="config"),
    path("status/", core_views.StatusView.as_view(), name="status"),
    path("", include(openapi_urls)),
    path(
        "auth/session/login/",
        views.SessionLoginView.as_view(),
        name="session-login",
    ),
    path(
        "auth/session/logout/",
        views.SessionLogoutView.as_view(),
        name="session-logout",
    ),
    path(
        "auth/token/refresh/",
        views.TokenRefreshView.as_view(),
        name="token-refresh",
    ),
    path("users/me/", views.CurrentUserView.as_view(), name="current-user"),
    *router.urls,
]

dab_urls = [
    path("", include(dab_urls)),
    path("", include(resource_api_urls)),
]

v1_urls = eda_v1_urls + dab_urls

urlpatterns = [
    path("v1/", include(v1_urls)),
    path("v1/", views.ApiV1RootView.as_view(), name="api-v1-root"),
    path("", views.ApiRootView.as_view(), name="api-root"),
]
