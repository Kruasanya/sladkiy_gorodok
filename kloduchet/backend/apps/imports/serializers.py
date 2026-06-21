from rest_framework import serializers

from .models import ImportBatch


class ImportBatchSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = ImportBatch
        fields = [
            "id",
            "organization",
            "organization_name",
            "data_type",
            "status",
            "original_filename",
            "sha256",
            "file_size",
            "period_start",
            "period_end",
            "row_count",
            "amount_total",
            "error_message",
            "warnings",
            "created_at",
            "started_at",
            "completed_at",
        ]
        read_only_fields = [f for f in fields if f not in ("organization", "data_type")]


class ImportUploadSerializer(serializers.Serializer):
    organization = serializers.UUIDField()
    data_type = serializers.ChoiceField(choices=ImportBatch.DATA_TYPE_CHOICES)
    file = serializers.FileField()
