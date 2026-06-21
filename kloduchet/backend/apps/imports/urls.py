from rest_framework.routers import DefaultRouter

from .views import ImportBatchViewSet

router = DefaultRouter()
router.register("", ImportBatchViewSet, basename="import")

urlpatterns = router.urls
