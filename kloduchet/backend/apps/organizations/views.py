from rest_framework import viewsets

from .models import AuditEvent, Organization
from .serializers import OrganizationSerializer


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer

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
