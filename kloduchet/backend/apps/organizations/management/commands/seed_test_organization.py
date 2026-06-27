"""Генерирует синтетические продажи/оплаты/банковские транзакции для тестовой организации.

Используется для демо-доступа «тестового клиента»: данные правдоподобны по форме
(контрагенты, номенклатура, суммы), но не являются реальными цифрами — их не нужно
загружать через импорт файлов вручную.
"""

import hashlib
import random
import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.banking.models import BankTransaction
from apps.imports.models import ImportBatch, StoredFile
from apps.organizations.models import Organization
from apps.payments.models import PaymentRecord
from apps.sales.models import SaleRecord

LEGAL_ENTITIES = ["ООО Ромашка", "ООО Лютик", "ИП Соколов"]
NOMENCLATURE = [
    "Конфеты ассорти 1кг",
    "Печенье сдобное 0.5кг",
    "Зефир ванильный 0.4кг",
    "Пряники тульские 1кг",
    "Шоколад молочный 0.1кг",
]
COUNTERPARTIES = ["Магазин у дома", "Сладкий мир", "ТД Северный", "Фасоль и Ко", "Гастроном №3"]
BANK_COUNTERPARTIES = COUNTERPARTIES + ["Поставщик упаковки", "Аренда помещения", "ФНС"]


class Command(BaseCommand):
    help = "Создаёт тестовую организацию с синтетическими данными для демо-доступа."

    def add_arguments(self, parser):
        parser.add_argument("--org-name", default="Тестовая компания")
        parser.add_argument("--months", type=int, default=6)
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Удалить ранее сгенерированные записи этой организации перед генерацией.",
        )

    def handle(self, *args, **options):
        org_name = options["org_name"]
        months = options["months"]
        rng = random.Random(f"seed-test-org-{org_name}")

        organization, created = Organization.objects.get_or_create(
            name=org_name,
            defaults={
                "legal_name": "ООО «Тестовая компания»",
                "inn": "7700000000",
                "kpp": "770001001",
                "is_active": True,
                "is_test": True,
            },
        )
        if not organization.is_test:
            organization.is_test = True
            organization.save(update_fields=["is_test"])

        if options["reset"]:
            SaleRecord.objects.filter(organization=organization).delete()
            PaymentRecord.objects.filter(organization=organization).delete()
            BankTransaction.objects.filter(organization=organization).delete()
            ImportBatch.objects.filter(organization=organization).delete()

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30 * months)

        with transaction.atomic():
            sales_batch = self._make_batch(organization, "sales")
            payments_batch = self._make_batch(organization, "payments")
            bank_batch = self._make_batch(organization, "bank")

            sales = self._build_sales(organization, sales_batch, start_date, end_date, rng)
            payments = self._build_payments(organization, payments_batch, start_date, end_date, rng)
            bank_rows = self._build_bank(organization, bank_batch, start_date, end_date, rng)

            SaleRecord.objects.bulk_create(sales, batch_size=500)
            PaymentRecord.objects.bulk_create(payments, batch_size=500)
            BankTransaction.objects.bulk_create(bank_rows, batch_size=500)

        self.stdout.write(
            self.style.SUCCESS(
                f"Организация «{organization.name}» ({'создана' if created else 'обновлена'}): "
                f"{len(sales)} продаж, {len(payments)} оплат, {len(bank_rows)} банковских проводок."
            )
        )

    def _make_batch(self, organization, data_type) -> ImportBatch:
        fake_bytes = f"seed-{organization.id}-{data_type}-{uuid.uuid4()}".encode()
        stored_file = StoredFile.objects.create(
            storage_path="seed:synthetic",
            original_filename=f"seed_{data_type}.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            size=0,
            sha256=hashlib.sha256(fake_bytes).hexdigest(),
        )
        return ImportBatch.objects.create(
            organization=organization,
            data_type=data_type,
            status="completed",
            original_filename=stored_file.original_filename,
            stored_file=stored_file,
            sha256=stored_file.sha256,
            file_size=0,
            row_count=0,
        )

    def _build_sales(self, organization, batch, start_date, end_date, rng):
        rows = []
        current = start_date
        doc_counter = 1
        while current <= end_date:
            if current.weekday() < 6:
                for _ in range(rng.randint(2, 6)):
                    legal_entity = rng.choice(LEGAL_ENTITIES)
                    is_return = rng.random() < 0.05
                    quantity = Decimal(str(round(rng.uniform(5, 80), 2)))
                    amount = Decimal(str(round(float(quantity) * rng.uniform(150, 600), 2)))
                    if is_return:
                        quantity, amount = -quantity, -amount
                    rows.append(
                        SaleRecord(
                            organization=organization,
                            import_batch=batch,
                            counterparty_raw=rng.choice(COUNTERPARTIES),
                            legal_entity=legal_entity,
                            contract_number=f"Д-{legal_entity[:3].upper()}-{rng.randint(1, 9)}",
                            sales_doc_type="Корректировка реализации" if is_return else "Реализация",
                            sales_doc_number=str(doc_counter),
                            sale_date=current,
                            nomenclature=rng.choice(NOMENCLATURE),
                            quantity=quantity,
                            amount=amount,
                        )
                    )
                    doc_counter += 1
            current += timedelta(days=1)
        return rows

    def _build_payments(self, organization, batch, start_date, end_date, rng):
        rows = []
        current = start_date
        doc_counter = 1
        while current <= end_date:
            if current.weekday() < 6 and rng.random() < 0.7:
                for _ in range(rng.randint(1, 3)):
                    legal_entity = rng.choice(LEGAL_ENTITIES)
                    amount = Decimal(str(round(rng.uniform(5000, 60000), 2)))
                    rows.append(
                        PaymentRecord(
                            organization=organization,
                            import_batch=batch,
                            counterparty_raw=rng.choice(COUNTERPARTIES),
                            legal_entity=legal_entity,
                            contract_number=f"Д-{legal_entity[:3].upper()}-{rng.randint(1, 9)}",
                            payment_doc_number=str(doc_counter),
                            payment_date=current,
                            amount=amount,
                        )
                    )
                    doc_counter += 1
            current += timedelta(days=1)
        return rows

    def _build_bank(self, organization, batch, start_date, end_date, rng):
        rows = []
        current = start_date
        while current <= end_date:
            for _ in range(rng.randint(1, 4)):
                is_credit = rng.random() < 0.6
                amount = Decimal(str(round(rng.uniform(3000, 80000), 2)))
                rows.append(
                    BankTransaction(
                        organization=organization,
                        import_batch=batch,
                        operation_date=current,
                        document_number=str(rng.randint(100000, 999999)),
                        debit=Decimal("0") if is_credit else amount,
                        credit=amount if is_credit else Decimal("0"),
                        amount=amount,
                        direction="credit" if is_credit else "debit",
                        counterparty_name=rng.choice(BANK_COUNTERPARTIES),
                        payment_purpose="Оплата по договору" if is_credit else "Оплата поставщику",
                    )
                )
            current += timedelta(days=1)
        return rows
