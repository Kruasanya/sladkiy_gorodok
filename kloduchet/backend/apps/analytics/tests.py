from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.imports.models import ImportBatch, StoredFile
from apps.organizations.models import Organization
from apps.payments.models import PaymentRecord
from apps.sales.models import SaleRecord

User = get_user_model()


def _make_batch(org, data_type="sales"):
    stored_file = StoredFile.objects.create(
        storage_path="/tmp/fake", original_filename="fake.xls", size=1, sha256="hash"
    )
    return ImportBatch.objects.create(
        organization=org,
        data_type=data_type,
        status="completed",
        original_filename="fake.xls",
        stored_file=stored_file,
        sha256=f"hash-{data_type}-{org.id}",
        file_size=1,
    )


class AnalyticsFixtureMixin:
    def setUp(self):
        self.org_a = Organization.objects.create(name="Организация А")
        self.org_b = Organization.objects.create(name="Организация Б")
        self.user = User.objects.create_user("owner", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        sales_batch_a = _make_batch(self.org_a, "sales")
        sales_batch_b = _make_batch(self.org_b, "sales")
        payments_batch_a = _make_batch(self.org_a, "payments")

        SaleRecord.objects.create(
            organization=self.org_a,
            import_batch=sales_batch_a,
            sale_date="2026-01-05",
            legal_entity="ООО Ромашка",
            contract_number="Д-1",
            nomenclature="Товар А",
            quantity=10,
            amount=1000,
            sales_doc_number="1",
        )
        SaleRecord.objects.create(
            organization=self.org_a,
            import_batch=sales_batch_a,
            sale_date="2026-02-10",
            legal_entity="ООО Ромашка",
            contract_number="Д-1",
            nomenclature="Товар Б",
            quantity=5,
            amount=500,
            sales_doc_number="2",
        )
        SaleRecord.objects.create(
            organization=self.org_b,
            import_batch=sales_batch_b,
            sale_date="2026-01-05",
            legal_entity="ООО Незабудка",
            contract_number="Д-2",
            nomenclature="Товар А",
            quantity=1,
            amount=2000,
            sales_doc_number="3",
        )
        PaymentRecord.objects.create(
            organization=self.org_a,
            import_batch=payments_batch_a,
            payment_date="2026-01-06",
            legal_entity="ООО Ромашка",
            contract_number="Д-1",
            amount=300,
        )


class SalesTimelineTests(AnalyticsFixtureMixin, TestCase):
    def test_anonymous_access_is_forbidden(self):
        client = APIClient()
        response = client.get("/api/analytics/sales/timeline")
        self.assertEqual(response.status_code, 403)

    def test_timeline_groups_by_month_for_all_organizations(self):
        response = self.client.get("/api/analytics/sales/timeline?group=month")
        rows = {str(row["period"]): row["amount_total"] for row in response.data["rows"]}
        self.assertEqual(float(rows["2026-01-01"]), 3000.0)  # 1000 (org A) + 2000 (org B)
        self.assertEqual(float(rows["2026-02-01"]), 500.0)

    def test_timeline_filters_by_organization(self):
        response = self.client.get(f"/api/analytics/sales/timeline?organization={self.org_a.id}")
        total = sum(float(row["amount_total"]) for row in response.data["rows"])
        self.assertEqual(total, 1500.0)

    def test_timeline_filters_by_date_range(self):
        response = self.client.get(
            "/api/analytics/sales/timeline?date_from=2026-02-01&date_to=2026-02-28"
        )
        total = sum(float(row["amount_total"]) for row in response.data["rows"])
        self.assertEqual(total, 500.0)


class SalesProductsTests(AnalyticsFixtureMixin, TestCase):
    def test_average_price_and_share_calculated_correctly(self):
        response = self.client.get(f"/api/analytics/sales/products?organization={self.org_a.id}")
        rows = {row["nomenclature"]: row for row in response.data["rows"]}
        self.assertEqual(rows["Товар А"]["average_price"], 100.0)
        self.assertAlmostEqual(rows["Товар А"]["share_of_total"], 1000 / 1500)


class SalesVsPaymentsTests(AnalyticsFixtureMixin, TestCase):
    def test_difference_and_payment_share_for_contract(self):
        response = self.client.get("/api/analytics/sales-vs-payments")
        row = next(r for r in response.data["rows"] if r["contract_number"] == "Д-1")
        self.assertEqual(float(row["sales_total"]), 1500.0)
        self.assertEqual(float(row["payments_total"]), 300.0)
        self.assertEqual(float(row["difference"]), 1200.0)

    def test_response_includes_mandatory_disclaimer(self):
        response = self.client.get("/api/analytics/sales-vs-payments")
        self.assertIn("не учитывает", response.data["disclaimer"])
        self.assertNotIn("задолженность", response.data["disclaimer"].lower())


class ExportTests(AnalyticsFixtureMixin, TestCase):
    def test_sales_timeline_export_returns_xlsx(self):
        response = self.client.get("/api/exports/sales/timeline")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_export_requires_authentication(self):
        client = APIClient()
        response = client.get("/api/exports/sales/timeline")
        self.assertEqual(response.status_code, 403)
