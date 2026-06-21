from rest_framework import serializers

from .models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "legal_name",
            "inn",
            "kpp",
            "is_active",
            "created_at",
            "updated_at",
        ]
