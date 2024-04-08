from django.urls import path

from . import views

urlpatterns = [
    path("status/", views.StatusView.as_view()),
    path("_healthz", views.HealthView.as_view()),
]
