from django.db import models

from apps.imports.models import ImportBatch
from apps.organizations.models import Organization


class SaleRecord(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="sale_records")
    import_batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="sale_records")

    counterparty_raw = models.CharField(max_length=255, null=True, blank=True)
    legal_entity = models.CharField(max_length=255, null=True, blank=True)
    brand = models.CharField(max_length=100, null=True, blank=True)
    store_location_raw = models.CharField(max_length=255, null=True, blank=True)
    city_or_area = models.CharField(max_length=255, null=True, blank=True)

    contract_raw = models.CharField(max_length=255, null=True, blank=True)
    contract_number = models.CharField(max_length=100, null=True, blank=True)
    contract_date = models.DateField(null=True, blank=True)

    sales_doc_raw = models.CharField(max_length=255, null=True, blank=True)
    sales_doc_type = models.CharField(max_length=100, null=True, blank=True)
    sales_doc_number = models.CharField(max_length=100, null=True, blank=True)
    sales_doc_date = models.DateField(null=True, blank=True)

    sale_date = models.DateField(null=True, blank=True)
    nomenclature = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    period_label = models.CharField(max_length=100, null=True, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    source_file = models.CharField(max_length=255, null=True, blank=True)
    source_file_path = models.CharField(max_length=512, null=True, blank=True)
    source_file_hash = models.CharField(max_length=64, null=True, blank=True)
    source_sheet = models.CharField(max_length=100, null=True, blank=True)
    source_row_number = models.IntegerField(null=True, blank=True)
    source_quantity_column = models.CharField(max_length=100, null=True, blank=True)
    source_amount_column = models.CharField(max_length=100, null=True, blank=True)

    record_fingerprint = models.CharField(max_length=64, db_index=True, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "sale_date"]),
            models.Index(fields=["organization", "nomenclature"]),
            models.Index(fields=["organization", "legal_entity"]),
            models.Index(fields=["organization", "contract_number"]),
        ]
