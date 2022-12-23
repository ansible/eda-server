from rest_framework import routers

from . import views

router = routers.SimpleRouter(trailing_slash=False)
router.register("extra_vars", views.ExtraVarViewSet)
router.register("playbooks", views.PlaybookViewSet)

urlpatterns = [
    *router.urls,
]
