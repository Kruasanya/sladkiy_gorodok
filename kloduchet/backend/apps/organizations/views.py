from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AuditEvent, Organization
from .serializers import OrganizationSerializer


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    http_method_names = ["get", "post", "patch", "put", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in {"1", "true", "yes"})
        return qs

    def perform_create(self, serializer):
        instance = serializer.save()
        AuditEvent.objects.create(
            user=self.request.user,
            entity_type="Organization",
            entity_id=str(instance.id),
            action="create",
            new_values=OrganizationSerializer(instance).data,
        )

    def perform_update(self, serializer):
        old_values = OrganizationSerializer(serializer.instance).data
        instance = serializer.save()
        AuditEvent.objects.create(
            user=self.request.user,
            entity_type="Organization",
            entity_id=str(instance.id),
            action="update",
            old_values=old_values,
            new_values=OrganizationSerializer(instance).data,
        )

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        instance = self.get_object()
        old_values = OrganizationSerializer(instance).data
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        AuditEvent.objects.create(
            user=self.request.user,
            entity_type="Organization",
            entity_id=str(instance.id),
            action="deactivate",
            old_values=old_values,
            new_values=OrganizationSerializer(instance).data,
        )
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        instance = self.get_object()
        old_values = OrganizationSerializer(instance).data
        instance.is_active = True
        instance.save(update_fields=["is_active", "updated_at"])
        AuditEvent.objects.create(
            user=self.request.user,
            entity_type="Organization",
            entity_id=str(instance.id),
            action="activate",
            old_values=old_values,
            new_values=OrganizationSerializer(instance).data,
        )
        return Response(self.get_serializer(instance).data)
