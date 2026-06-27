from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from apps.organizations.scoping import DenyTestClient

from .models import ProductReference
from .serializers import ProductReferenceSerializer


class ProductReferenceViewSet(ModelViewSet):
    queryset = ProductReference.objects.all()
    serializer_class = ProductReferenceSerializer
    http_method_names = ["get", "post", "patch", "put", "head", "options"]
    permission_classes = [IsAuthenticated, DenyTestClient]
