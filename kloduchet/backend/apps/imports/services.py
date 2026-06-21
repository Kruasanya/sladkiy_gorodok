from __future__ import annotations

import hashlib
import tempfile
import uuid
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.banking.models import BankTransaction
from apps.payments.models import PaymentRecord
from apps.sales.models import SaleRecord

from .models import ImportBatch, StoredFile

ALLOWED_EXTENSIONS = {".xls", ".xlsx"}

EXTENSION_BY_DATA_TYPE = {
    "sales": ".xls",
    "payments": ".xls",
    "bank": ".xlsx",
}


def _to_date(value):
    if value is None:
        return None
    try:
        if value != value:  # NaT / NaN check
            return None
    except TypeError:
        pass
    return value.date() if hasattr(value, "date") else value


def _build_sale_records(batch, df):
    return [
        SaleRecord(
            organization=batch.organization,
            import_batch=batch,
            counterparty_raw=row.get("counterparty_raw"),
            legal_entity=row.get("legal_entity"),
            brand=row.get("brand"),
            store_location_raw=row.get("store_location_raw"),
            city_or_area=row.get("city_or_area"),
            contract_raw=row.get("contract_raw"),
            contract_number=row.get("contract_number"),
            contract_date=_to_date(row.get("contract_date")),
            sales_doc_raw=row.get("sales_doc_raw"),
            sales_doc_type=row.get("sales_doc_type"),
            sales_doc_number=row.get("sales_doc_number"),
            sales_doc_date=_to_date(row.get("sales_doc_date")),
            sale_date=_to_date(row.get("sale_date")),
            nomenclature=row.get("nomenclature"),
            quantity=row.get("quantity") or 0,
            amount=row.get("amount") or 0,
            period_label=row.get("period_label"),
            period_start=_to_date(row.get("period_start")),
            period_end=_to_date(row.get("period_end")),
            source_file=row.get("source_file"),
            source_file_path=row.get("source_file_path"),
            source_file_hash=row.get("source_file_hash"),
            source_sheet=row.get("source_sheet"),
            source_row_number=row.get("source_row_number"),
            source_quantity_column=str(row.get("source_quantity_column")),
            source_amount_column=str(row.get("source_amount_column")),
        )
        for row in df.to_dict("records")
    ]


def _build_payment_records(batch, df):
    return [
        PaymentRecord(
            organization=batch.organization,
            import_batch=batch,
            counterparty_raw=row.get("counterparty_raw"),
            legal_entity=row.get("legal_entity"),
            brand=row.get("brand"),
            store_location_raw=row.get("store_location_raw"),
            city_or_area=row.get("city_or_area"),
            contract_raw=row.get("contract_raw"),
            contract_number=row.get("contract_number"),
            contract_date=_to_date(row.get("contract_date")),
            payment_doc_raw=row.get("payment_doc_raw"),
            payment_doc_number=row.get("payment_doc_number"),
            payment_date=_to_date(row.get("payment_date")),
            amount=row.get("amount") or 0,
            period_label=row.get("period_label"),
            period_start=_to_date(row.get("period_start")),
            period_end=_to_date(row.get("period_end")),
            source_file=row.get("source_file"),
            source_file_path=row.get("source_file_path"),
            source_file_hash=row.get("source_file_hash"),
            source_sheet=row.get("source_sheet"),
            source_row_number=row.get("source_row_number"),
            source_column=str(row.get("source_column")),
        )
        for row in df.to_dict("records")
    ]


def _build_bank_records(batch, df):
    return [
        BankTransaction(
            organization=batch.organization,
            import_batch=batch,
            operation_date=_to_date(row.get("operation_date")),
            document_number=row.get("document_number"),
            debit=row.get("debit") or 0,
            credit=row.get("credit") or 0,
            amount=row.get("amount") or 0,
            direction=row.get("direction"),
            counterparty_name=row.get("counterparty_name"),
            counterparty_inn=row.get("counterparty_inn"),
            counterparty_kpp=row.get("counterparty_kpp"),
            counterparty_account=row.get("counterparty_account"),
            counterparty_bik=row.get("counterparty_bik"),
            counterparty_bank_name=row.get("counterparty_bank_name"),
            payment_purpose=row.get("payment_purpose"),
            debtor_code=row.get("debtor_code"),
            document_type=row.get("document_type"),
            source_file=row.get("source_file"),
            source_file_path=row.get("source_file_path"),
            source_file_hash=row.get("source_file_hash"),
            source_sheet=row.get("source_sheet"),
            source_row_number=row.get("source_row_number"),
        )
        for row in df.to_dict("records")
    ]


def _amount_total_for(data_type, result):
    if data_type == "bank":
        return result.amount_total, result.debit_total, result.credit_total
    return result.amount_total, None, None


# Реестр обработчиков по типу данных: модуль-адаптер пайплайна (см. tech_spec.md,
# раздел 6.3) + функция, строящая ORM-объекты из распарсенного DataFrame.
DATA_TYPE_HANDLERS = {
    "sales": {
        "adapter_module": "pipelines.sales_by_counterparties_adapter",
        "build_records": _build_sale_records,
        "related_name": "sale_records",
    },
    "payments": {
        "adapter_module": "pipelines.payments_adapter",
        "build_records": _build_payment_records,
        "related_name": "payment_records",
    },
    "bank": {
        "adapter_module": "pipelines.bank_adapter",
        "build_records": _build_bank_records,
        "related_name": "bank_transactions",
    },
}


def _sha256_of(file) -> str:
    digest = hashlib.sha256()
    for chunk in file.chunks():
        digest.update(chunk)
    file.seek(0)
    return digest.hexdigest()


def save_uploaded_file(upload) -> StoredFile:
    suffix = Path(upload.name).suffix.lower()
    sha256 = _sha256_of(upload)
    stored_name = f"{uuid.uuid4()}{suffix}"
    storage_dir = Path(settings.MEDIA_ROOT)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / stored_name

    with open(storage_path, "wb") as destination:
        for chunk in upload.chunks():
            destination.write(chunk)

    return StoredFile.objects.create(
        storage_path=str(storage_path),
        original_filename=upload.name,
        content_type=upload.content_type or "",
        size=upload.size,
        sha256=sha256,
    )


def create_import_batch(*, organization, data_type, stored_file, user) -> ImportBatch:
    return ImportBatch.objects.create(
        organization=organization,
        data_type=data_type,
        status="uploaded",
        original_filename=stored_file.original_filename,
        stored_file=stored_file,
        sha256=stored_file.sha256,
        file_size=stored_file.size,
        created_by=user,
    )


def run_import(batch: ImportBatch) -> ImportBatch:
    """
    Синхронная обработка пакета загрузки (в MVP без Celery/Redis — см. README
    раздел «Чем эта демо-версия отличается от tech_spec.md»).
    """
    import importlib

    handler = DATA_TYPE_HANDLERS.get(batch.data_type)
    if handler is None:
        batch.status = "failed"
        batch.error_message = f"Тип данных «{batch.data_type}» пока не поддерживается."
        batch.save()
        return batch

    completed_duplicate = (
        ImportBatch.objects.filter(
            organization=batch.organization,
            data_type=batch.data_type,
            sha256=batch.sha256,
            status="completed",
        )
        .exclude(pk=batch.pk)
        .exists()
    )
    if completed_duplicate:
        batch.status = "failed"
        batch.error_message = "Файл с такой же контрольной суммой уже успешно загружен для этой организации и типа данных."
        batch.save()
        return batch

    batch.status = "processing"
    batch.started_at = timezone.now()
    batch.save()

    adapter = importlib.import_module(handler["adapter_module"])

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_source = Path(tmp_dir) / batch.original_filename
        tmp_source.write_bytes(Path(batch.stored_file.storage_path).read_bytes())

        result = adapter.process_file(source_path=tmp_source, output_dir=Path(tmp_dir))

        if result.errors:
            batch.status = "failed"
            batch.error_message = "; ".join(result.errors)
            batch.warnings = result.warnings
            batch.completed_at = timezone.now()
            batch.save()
            return batch

        df = adapter.dataframe_from_result(result)
        amount_total, debit_total, credit_total = _amount_total_for(batch.data_type, result)

        try:
            with transaction.atomic():
                records = handler["build_records"](batch, df)
                model = type(records[0]) if records else None
                if model is not None:
                    model.objects.bulk_create(records, batch_size=1000)

                batch.row_count = len(records)
                batch.amount_total = amount_total
                batch.debit_total = debit_total
                batch.credit_total = credit_total
                batch.period_start = _to_date(result.period_start)
                batch.period_end = _to_date(result.period_end)
                batch.warnings = result.warnings
                batch.status = "completed"
                batch.completed_at = timezone.now()
                batch.save()
        except Exception as exc:
            batch.status = "failed"
            batch.error_message = f"Ошибка записи в базу данных, импорт отменен целиком: {exc}"
            batch.completed_at = timezone.now()
            batch.save()

    return batch


def dispatch_import(batch: ImportBatch) -> ImportBatch:
    """
    Запускает обработку пакета. При настроенном CELERY_BROKER_URL (см.
    docker-compose.yml и tech_spec.md раздел 8) задача уходит в очередь и
    обрабатывается worker'ом — интерфейс получает статус "queued" и опрашивает
    пакет, не блокируясь. Без брокера (локальный запуск без Docker, см. README)
    обработка выполняется синхронно в этом же запросе.
    """
    from django.conf import settings

    if settings.CELERY_ENABLED:
        from .tasks import run_import_task

        batch.status = "queued"
        batch.save()
        run_import_task.delay(str(batch.pk))
        return batch

    return run_import(batch)


def cancel_import(batch: ImportBatch) -> ImportBatch:
    if batch.status != "completed":
        raise ValueError("Отменить можно только полностью завершенный пакет.")

    handler = DATA_TYPE_HANDLERS[batch.data_type]

    with transaction.atomic():
        getattr(batch, handler["related_name"]).all().delete()
        batch.status = "cancelled"
        batch.save()

    return batch
