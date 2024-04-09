from django.urls import path

from . import views

urlpatterns = [
    path("_healthz", views.HealthView.as_view()),
]
