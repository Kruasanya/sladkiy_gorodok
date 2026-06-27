from rest_framework.viewsets import ModelViewSet

from .models import ProductReference
from .serializers import ProductReferenceSerializer


class ProductReferenceViewSet(ModelViewSet):
    queryset = ProductReference.objects.all()
    serializer_class = ProductReferenceSerializer
    http_method_names = ["get", "post", "patch", "put", "head", "options"]
