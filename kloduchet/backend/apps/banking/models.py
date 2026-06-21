from django.db import models

from apps.imports.models import ImportBatch
from apps.organizations.models import Organization


class BankTransaction(models.Model):
    DIRECTION_CHOICES = [("credit", "Поступление"), ("debit", "Списание")]

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="bank_transactions")
    import_batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="bank_transactions")

    operation_date = models.DateField(null=True, blank=True)
    document_number = models.CharField(max_length=100, null=True, blank=True)
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, null=True, blank=True)

    counterparty_name = models.CharField(max_length=255, null=True, blank=True)
    counterparty_inn = models.CharField(max_length=20, null=True, blank=True)
    counterparty_kpp = models.CharField(max_length=20, null=True, blank=True)
    counterparty_account = models.CharField(max_length=40, null=True, blank=True)
    counterparty_bik = models.CharField(max_length=20, null=True, blank=True)
    counterparty_bank_name = models.CharField(max_length=255, null=True, blank=True)
    payment_purpose = models.TextField(null=True, blank=True)
    debtor_code = models.CharField(max_length=100, null=True, blank=True)
    document_type = models.CharField(max_length=100, null=True, blank=True)

    source_file = models.CharField(max_length=255, null=True, blank=True)
    source_file_path = models.CharField(max_length=512, null=True, blank=True)
    source_file_hash = models.CharField(max_length=64, null=True, blank=True)
    source_sheet = models.CharField(max_length=100, null=True, blank=True)
    source_row_number = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "operation_date"]),
            models.Index(fields=["organization", "direction"]),
            models.Index(fields=["organization", "counterparty_inn"]),
        ]
