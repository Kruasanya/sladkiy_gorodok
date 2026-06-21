import uuid

from django.conf import settings
from django.db import models

from apps.organizations.models import Organization


class StoredFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    storage_path = models.CharField(max_length=512)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.BigIntegerField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class ImportBatch(models.Model):
    DATA_TYPE_CHOICES = [
        ("sales", "Продажи по контрагентам"),
        ("payments", "Продажи по контрагентам по оплате"),
        ("bank", "Банковские выписки"),
    ]
    STATUS_CHOICES = [
        ("uploaded", "Загружен"),
        ("queued", "В очереди"),
        ("processing", "Обрабатывается"),
        ("validated", "Проверен"),
        ("completed", "Завершен"),
        ("failed", "Ошибка"),
        ("cancelled", "Отменен"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="import_batches")
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="uploaded")
    original_filename = models.CharField(max_length=255)
    stored_file = models.ForeignKey(StoredFile, on_delete=models.PROTECT, related_name="import_batches")
    sha256 = models.CharField(max_length=64)
    file_size = models.BigIntegerField()
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    row_count = models.IntegerField(default=0)
    amount_total = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    debit_total = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    credit_total = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    error_message = models.TextField(blank=True)
    warnings = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "data_type", "sha256"],
                condition=models.Q(status="completed"),
                name="unique_completed_batch_per_org_type_hash",
            )
        ]
