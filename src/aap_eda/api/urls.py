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
from rest_framework_simplejwt import views as jwt_views

from . import views

router = routers.SimpleRouter()
# basename has to be set when queryset is user-dependent
# which is any model with permissions
router.register("extra-vars", views.ExtraVarViewSet, basename="extravar")
router.register("projects", views.ProjectViewSet, basename="project")
router.register("rulebooks", views.RulebookViewSet, basename="rulebook")
router.register(
    "roles", views.RoleViewSet, basename="role"
)  # deprecated, DAB RBAC uses roledefinition
router.register("activations", views.ActivationViewSet, basename="activation")
router.register(
    "activation-instances",
    views.ActivationInstanceViewSet,
    basename="activationinstance",
)
router.register("audit-rules", views.AuditRuleViewSet, basename="auditrule")
router.register("users", views.UserViewSet, basename="user")
router.register(
    "event-streams", views.EventStreamViewSet, basename="eventstream"
)
router.register(
    "users/me/awx-tokens",
    views.CurrentUserAwxTokenViewSet,
    basename="controller-token",
)
router.register("credentials", views.CredentialViewSet, basename="credential")
router.register(
    "decision-environments",
    views.DecisionEnvironmentViewSet,
    basename="decisionenvironment",
)
router.register(
    "organizations", views.OrganizationViewSet, basename="organization"
)
router.register("teams", views.TeamViewSet, basename="team")

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
        "docs",
        SpectacularSwaggerView.as_view(url_name="openapi-json"),
        name="openapi-docs",
    ),
    path(
        "redoc",
        SpectacularRedocView.as_view(url_name="openapi-json"),
        name="openapi-redoc",
    ),
]

v1_urls = [
    path("", include(dab_urls)),
    path("", include(resource_api_urls)),
    path("", include(openapi_urls)),
    path("auth/session/login/", views.SessionLoginView.as_view()),
    path("auth/session/logout/", views.SessionLogoutView.as_view()),
    path(
        "auth/token/refresh/",
        jwt_views.TokenRefreshView.as_view(),
        name="token_refresh",
    ),
    path("users/me/", views.CurrentUserView.as_view()),
    *router.urls,
]

urlpatterns = [
    path("v1/", include(v1_urls)),
]
