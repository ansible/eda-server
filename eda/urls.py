from django.urls import include, path

from . import api_urls

from . import views


urlpatterns = []

urlpatterns += api_urls.urlpatterns

urlpatterns += [
    path("chat/", views.index, name="index"),
    path("chat/<str:room_name>/", views.room, name="room"),
]

__all__ = ["urlpatterns"]



