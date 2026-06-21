"""
Тесты раздела 19.1 tech_spec.md, относящиеся к импорту.

Парсинг исходных Excel-файлов — забота уже существующих пайплайнов
(см. `Данные/Пайплайны обработки данных`), их бизнес-правила здесь не
переписываются и не перепроверяются. Эти тесты проверяют то, что относится
к Django-стороне: выбор организации, защита от дублей, атомарность записи,
отмену пакета — для чего адаптер пайплайна подменяется фиктивным результатом
с маленьким набором строк (раздел 19.3: "реальные финансовые файлы не должны
требоваться для запуска unit-тестов").
"""

from __future__ import annotations

import pandas as pd
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from unittest import mock
from rest_framework.test import APIClient

from apps.organizations.models import Organization
from apps.sales.models import SaleRecord

from . import services
from .models import ImportBatch
from pipelines import sales_by_counterparties_adapter as adapter

User = get_user_model()


def _fake_sales_result(rows=2, with_error=False):
    df = pd.DataFrame(
        [
            {
                "counterparty_raw": "ООО Ромашка",
                "legal_entity": "ООО Ромашка",
                "brand": None,
                "store_location_raw": None,
                "city_or_area": None,
                "contract_raw": None,
                "contract_number": "Д-1",
                "contract_date": pd.NaT,
                "sales_doc_raw": None,
                "sales_doc_type": "Реализация",
                "sales_doc_number": f"{i}",
                "sales_doc_date": pd.Timestamp("2026-01-0%d" % (i + 1)),
                "sale_date": pd.Timestamp("2026-01-0%d" % (i + 1)),
                "nomenclature": "Товар А",
                "quantity": 10,
                "amount": 1000,
                "period_label": "Январь 2026",
                "period_start": pd.Timestamp("2026-01-01"),
                "period_end": pd.Timestamp("2026-01-31"),
                "source_file": "test.xls",
                "source_file_path": "test.xls",
                "source_file_hash": "fakehash",
                "source_sheet": "Лист_1",
                "source_row_number": i,
                "source_quantity_column": "01.01.26",
                "source_amount_column": "01.01.26",
            }
            for i in range(rows)
        ]
    )
    errors = ["Тестовая ошибка"] if with_error else []
    return adapter.ProcessResult(
        parquet_path="" if with_error else "/tmp/fake.parquet",
        row_count=0 if with_error else rows,
        amount_total=0 if with_error else 1000 * rows,
        quantity_total=0 if with_error else 10 * rows,
        warnings=[],
        errors=errors,
        period_start=None if with_error else pd.Timestamp("2026-01-01"),
        period_end=None if with_error else pd.Timestamp("2026-01-31"),
        source_filename="test.xls",
        source_sha256="fakehash",
    ), df


class ImportServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="ООО Ромашка")
        self.user = User.objects.create_user("owner", password="pass12345")
        self.stored_file_upload = SimpleUploadedFile("test.xls", b"fake-bytes")

    def _create_batch(self):
        stored_file = services.save_uploaded_file(self.stored_file_upload)
        return services.create_import_batch(
            organization=self.org, data_type="sales", stored_file=stored_file, user=self.user
        )

    def test_successful_import_creates_sale_records_and_completes_batch(self):
        batch = self._create_batch()
        result, df = _fake_sales_result(rows=3)

        with mock.patch.object(adapter, "process_file", return_value=result), mock.patch.object(
            adapter, "dataframe_from_result", return_value=df
        ):
            batch = services.run_import(batch)

        batch.refresh_from_db()
        self.assertEqual(batch.status, "completed")
        self.assertEqual(batch.row_count, 3)
        self.assertEqual(SaleRecord.objects.filter(import_batch=batch).count(), 3)

    def test_duplicate_file_for_same_organization_and_type_is_rejected(self):
        batch1 = self._create_batch()
        result, df = _fake_sales_result(rows=1)
        with mock.patch.object(adapter, "process_file", return_value=result), mock.patch.object(
            adapter, "dataframe_from_result", return_value=df
        ):
            services.run_import(batch1)

        stored_file2 = services.save_uploaded_file(SimpleUploadedFile("test.xls", b"fake-bytes"))
        batch2 = services.create_import_batch(
            organization=self.org, data_type="sales", stored_file=stored_file2, user=self.user
        )
        batch2 = services.run_import(batch2)

        self.assertEqual(batch2.status, "failed")
        self.assertIn("уже успешно загружен", batch2.error_message)

    def test_pipeline_error_leaves_no_rows_in_database(self):
        batch = self._create_batch()
        result, df = _fake_sales_result(rows=2, with_error=True)

        with mock.patch.object(adapter, "process_file", return_value=result), mock.patch.object(
            adapter, "dataframe_from_result", return_value=df
        ):
            batch = services.run_import(batch)

        batch.refresh_from_db()
        self.assertEqual(batch.status, "failed")
        self.assertEqual(SaleRecord.objects.filter(import_batch=batch).count(), 0)

    def test_cancel_only_allowed_for_completed_batch(self):
        batch = self._create_batch()
        with self.assertRaises(ValueError):
            services.cancel_import(batch)

    def test_cancel_deletes_records_and_marks_batch_cancelled(self):
        batch = self._create_batch()
        result, df = _fake_sales_result(rows=2)
        with mock.patch.object(adapter, "process_file", return_value=result), mock.patch.object(
            adapter, "dataframe_from_result", return_value=df
        ):
            batch = services.run_import(batch)

        batch = services.cancel_import(batch)

        self.assertEqual(batch.status, "cancelled")
        self.assertEqual(SaleRecord.objects.filter(import_batch=batch).count(), 0)


class ImportApiTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="ООО Ромашка")
        self.user = User.objects.create_user("owner", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_upload_requires_organization(self):
        upload = SimpleUploadedFile("test.xls", b"fake-bytes")
        response = self.client.post(
            "/api/imports/", {"data_type": "sales", "file": upload}, format="multipart"
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_rejects_extension_mismatched_with_data_type(self):
        upload = SimpleUploadedFile("test.xlsx", b"fake-bytes")
        response = self.client.post(
            "/api/imports/",
            {"organization": str(self.org.id), "data_type": "sales", "file": upload},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_runs_pipeline_and_returns_completed_batch(self):
        result, df = _fake_sales_result(rows=2)
        upload = SimpleUploadedFile("test.xls", b"fake-bytes")

        with mock.patch.object(adapter, "process_file", return_value=result), mock.patch.object(
            adapter, "dataframe_from_result", return_value=df
        ):
            response = self.client.post(
                "/api/imports/",
                {"organization": str(self.org.id), "data_type": "sales", "file": upload},
                format="multipart",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["row_count"], 2)

    def test_batch_sha256_is_stored(self):
        upload = SimpleUploadedFile("test.xls", b"fake-bytes")
        stored_file = services.save_uploaded_file(upload)
        batch = services.create_import_batch(
            organization=self.org, data_type="sales", stored_file=stored_file, user=self.user
        )
        self.assertEqual(len(batch.sha256), 64)
        self.assertEqual(batch.sha256, stored_file.sha256)
