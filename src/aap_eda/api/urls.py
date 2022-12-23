from django.urls import include, path
from drf_spectacular.views import (
    SpectacularJSONAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
    SpectacularYAMLAPIView,
)
from rest_framework import routers

from . import views

router = routers.SimpleRouter(trailing_slash=False)
router.register("extra_vars", views.ExtraVarViewSet)
router.register("playbooks", views.PlaybookViewSet)

v1_urls = [
    *router.urls,
]

openapi_urls = [
    path(
        "openapi.json",
        SpectacularJSONAPIView.as_view(),
        name="openapi-json",
    ),
    path(
        "openapi.yaml",
        SpectacularYAMLAPIView.as_view(),
        name="openapi-jaml",
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

urlpatterns = [
    path("v1/", include(v1_urls)),
    path("", include(openapi_urls)),
]
