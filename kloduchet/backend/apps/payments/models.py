from django.db import models

from apps.imports.models import ImportBatch
from apps.organizations.models import Organization


class PaymentRecord(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="payment_records")
    import_batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="payment_records")

    counterparty_raw = models.CharField(max_length=255, null=True, blank=True)
    legal_entity = models.CharField(max_length=255, null=True, blank=True)
    brand = models.CharField(max_length=100, null=True, blank=True)
    store_location_raw = models.CharField(max_length=255, null=True, blank=True)
    city_or_area = models.CharField(max_length=255, null=True, blank=True)

    contract_raw = models.CharField(max_length=255, null=True, blank=True)
    contract_number = models.CharField(max_length=100, null=True, blank=True)
    contract_date = models.DateField(null=True, blank=True)

    payment_doc_raw = models.CharField(max_length=255, null=True, blank=True)
    payment_doc_number = models.CharField(max_length=100, null=True, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    period_label = models.CharField(max_length=100, null=True, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    source_file = models.CharField(max_length=255, null=True, blank=True)
    source_file_path = models.CharField(max_length=512, null=True, blank=True)
    source_file_hash = models.CharField(max_length=64, null=True, blank=True)
    source_sheet = models.CharField(max_length=100, null=True, blank=True)
    source_row_number = models.IntegerField(null=True, blank=True)
    source_column = models.CharField(max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "payment_date"]),
            models.Index(fields=["organization", "legal_entity"]),
            models.Index(fields=["organization", "contract_number"]),
        ]
