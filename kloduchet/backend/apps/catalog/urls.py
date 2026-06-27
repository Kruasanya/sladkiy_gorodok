from rest_framework.routers import DefaultRouter

from .views import ProductReferenceViewSet

router = DefaultRouter()
router.register("products", ProductReferenceViewSet, basename="product-reference")

urlpatterns = router.urls
