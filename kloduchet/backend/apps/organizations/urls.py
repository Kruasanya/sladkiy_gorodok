from rest_framework.routers import DefaultRouter

from .views import OrganizationViewSet, UserViewSet

router = DefaultRouter()
router.register("", OrganizationViewSet, basename="organization")

urlpatterns = router.urls

user_router = DefaultRouter()
user_router.register("", UserViewSet, basename="user")

urlpatterns_users = user_router.urls
