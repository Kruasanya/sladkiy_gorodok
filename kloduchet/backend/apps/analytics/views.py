from django.db.models import Case, DecimalField, Sum, Count, Q, When
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import ProductReference
from apps.payments.models import PaymentRecord
from apps.sales.models import SaleRecord

# Раздел 12.2-12.4 tech_spec.md: продажи ("Реализация") и возвраты/корректировки
# ("Корректировка реализации") должны быть видны отдельно, а не только net-суммой.
RETURNS_SUM = Sum(
    Case(
        When(sales_doc_type="Корректировка реализации", then="amount"),
        default=0,
        output_field=DecimalField(max_digits=18, decimal_places=2),
    )
)
GROSS_SALES_SUM = Sum(
    Case(
        When(~Q(sales_doc_type="Корректировка реализации"), then="amount"),
        default=0,
        output_field=DecimalField(max_digits=18, decimal_places=2),
    )
)

SALES_VS_PAYMENTS_DISCLAIMER = (
    "Показатель является сравнением продаж и оплат за выбранный период. Он не учитывает "
    "начальные остатки, сроки оплаты и точное распределение платежей по реализациям."
)

TRUNC_BY_GROUP = {
    "day": TruncDay,
    "week": TruncWeek,
    "month": TruncMonth,
}


def _filtered_queryset(request):
    qs = SaleRecord.objects.all()

    organizations = request.query_params.getlist("organization")
    if organizations:
        qs = qs.filter(organization_id__in=organizations)

    date_from = request.query_params.get("date_from")
    date_to = request.query_params.get("date_to")
    if date_from:
        qs = qs.filter(sale_date__gte=date_from)
    if date_to:
        qs = qs.filter(sale_date__lte=date_to)

    counterparty = request.query_params.get("counterparty")
    if counterparty:
        qs = qs.filter(counterparty_raw__icontains=counterparty)

    nomenclature = request.query_params.get("nomenclature")
    if nomenclature:
        qs = qs.filter(nomenclature__icontains=nomenclature)

    display_name = request.query_params.get("display_name")
    if display_name:
        raw_values = ProductReference.objects.filter(display_name=display_name).values_list(
            "nomenclature_raw", flat=True
        )
        qs = qs.filter(nomenclature__in=list(raw_values))

    contract_number = request.query_params.get("contract_number")
    if contract_number:
        qs = qs.filter(contract_number=contract_number)

    return qs


class SalesTimelineView(APIView):
    def get(self, request):
        group = request.query_params.get("group", "month")
        trunc = TRUNC_BY_GROUP.get(group, TruncMonth)

        qs = _filtered_queryset(request)
        rows = (
            qs.annotate(period=trunc("sale_date"))
            .values("period")
            .annotate(
                gross_sales_total=GROSS_SALES_SUM,
                returns_total=RETURNS_SUM,
                amount_total=Sum("amount"),
                quantity_total=Sum("quantity"),
                documents_count=Count("sales_doc_number", distinct=True),
            )
            .order_by("period")
        )

        return Response(
            {
                "group": group,
                "rows": [
                    {
                        "period": row["period"],
                        "gross_sales_total": row["gross_sales_total"] or 0,
                        "returns_total": row["returns_total"] or 0,
                        "amount_total": row["amount_total"] or 0,
                        "quantity_total": row["quantity_total"] or 0,
                        "documents_count": row["documents_count"] or 0,
                    }
                    for row in rows
                    if row["period"] is not None
                ],
            }
        )


class SalesProductsView(APIView):
    def get(self, request):
        qs = _filtered_queryset(request)
        total_amount = qs.aggregate(total=Sum("amount"))["total"] or 0
        display_name_by_raw = dict(
            ProductReference.objects.values_list("nomenclature_raw", "display_name")
        )

        rows = (
            qs.values("nomenclature")
            .annotate(
                gross_sales_total=GROSS_SALES_SUM,
                returns_total=RETURNS_SUM,
                amount_total=Sum("amount"),
                quantity_total=Sum("quantity"),
            )
            .order_by("-amount_total")
        )

        data = []
        for row in rows:
            quantity = row["quantity_total"] or 0
            amount = row["amount_total"] or 0
            data.append(
                {
                    "nomenclature": row["nomenclature"],
                    "display_name": display_name_by_raw.get(row["nomenclature"]),
                    "gross_sales_total": row["gross_sales_total"] or 0,
                    "returns_total": row["returns_total"] or 0,
                    "amount_total": amount,
                    "quantity_total": quantity,
                    "average_price": float(amount) / float(quantity) if quantity else None,
                    "share_of_total": float(amount) / float(total_amount) if total_amount else None,
                }
            )
        return Response({"rows": data, "amount_total": total_amount})


class SalesProductsTimeseriesView(APIView):
    """Графики продаж по товарам: динамика во времени с выбираемой агрегацией."""

    def get(self, request):
        group = request.query_params.get("group", "month")
        trunc = TRUNC_BY_GROUP.get(group, TruncMonth)
        metric = request.query_params.get("metric", "amount")
        if metric not in {"amount", "quantity"}:
            metric = "amount"
        dimension = request.query_params.get("dimension", "display_name")

        qs = _filtered_queryset(request)
        display_name_by_raw = dict(
            ProductReference.objects.values_list("nomenclature_raw", "display_name")
        )

        rows = (
            qs.annotate(period=trunc("sale_date"))
            .values("period", "nomenclature")
            .annotate(value=Sum(metric))
            .order_by("period")
        )

        series: dict[str, dict] = {}
        for row in rows:
            if row["period"] is None:
                continue
            key = (
                display_name_by_raw.get(row["nomenclature"]) or row["nomenclature"]
                if dimension == "display_name"
                else row["nomenclature"]
            )
            key = key or "—"
            entry = series.setdefault(key, {})
            entry[row["period"].isoformat()] = entry.get(row["period"].isoformat(), 0) + float(
                row["value"] or 0
            )

        periods = sorted({row["period"].isoformat() for row in rows if row["period"] is not None})
        result = [
            {"name": name, "points": [{"period": p, "value": values.get(p, 0)} for p in periods]}
            for name, values in series.items()
        ]

        return Response({"group": group, "metric": metric, "dimension": dimension, "series": result})


class SalesCounterpartiesView(APIView):
    def get(self, request):
        level = request.query_params.get("level", "legal_entity")
        if level not in {"legal_entity", "brand", "counterparty_raw", "contract_number"}:
            level = "legal_entity"

        qs = _filtered_queryset(request)
        total_amount = qs.aggregate(total=Sum("amount"))["total"] or 0

        rows = (
            qs.values(level)
            .annotate(
                gross_sales_total=GROSS_SALES_SUM,
                returns_total=RETURNS_SUM,
                amount_total=Sum("amount"),
                quantity_total=Sum("quantity"),
                documents_count=Count("sales_doc_number", distinct=True),
            )
            .order_by("-amount_total")
        )

        data = []
        for row in rows:
            amount = row["amount_total"] or 0
            data.append(
                {
                    "key": row[level],
                    "gross_sales_total": row["gross_sales_total"] or 0,
                    "returns_total": row["returns_total"] or 0,
                    "amount_total": amount,
                    "quantity_total": row["quantity_total"] or 0,
                    "documents_count": row["documents_count"] or 0,
                    "share_of_total": float(amount) / float(total_amount) if total_amount else None,
                }
            )
        return Response({"level": level, "rows": data, "amount_total": total_amount})


def _filtered_payments_queryset(request):
    qs = PaymentRecord.objects.all()

    organizations = request.query_params.getlist("organization")
    if organizations:
        qs = qs.filter(organization_id__in=organizations)

    date_from = request.query_params.get("date_from")
    date_to = request.query_params.get("date_to")
    if date_from:
        qs = qs.filter(payment_date__gte=date_from)
    if date_to:
        qs = qs.filter(payment_date__lte=date_to)

    counterparty = request.query_params.get("counterparty")
    if counterparty:
        qs = qs.filter(counterparty_raw__icontains=counterparty)

    contract_number = request.query_params.get("contract_number")
    if contract_number:
        qs = qs.filter(contract_number=contract_number)

    return qs


class SalesVsPaymentsView(APIView):
    """Раздел 12.5 tech_spec.md — агрегированное сравнение продаж и оплат."""

    def get(self, request):
        sales_qs = _filtered_queryset(request)
        payments_qs = _filtered_payments_queryset(request)

        sales_rows = sales_qs.values("organization_id", "legal_entity", "contract_number").annotate(
            sales_total=Sum("amount")
        )
        payments_rows = payments_qs.values("organization_id", "legal_entity", "contract_number").annotate(
            payments_total=Sum("amount")
        )

        combined: dict[tuple, dict] = {}
        for row in sales_rows:
            key = (row["organization_id"], row["legal_entity"], row["contract_number"])
            combined[key] = {
                "organization_id": row["organization_id"],
                "legal_entity": row["legal_entity"],
                "contract_number": row["contract_number"],
                "sales_total": row["sales_total"] or 0,
                "payments_total": 0,
            }
        for row in payments_rows:
            key = (row["organization_id"], row["legal_entity"], row["contract_number"])
            entry = combined.setdefault(
                key,
                {
                    "organization_id": row["organization_id"],
                    "legal_entity": row["legal_entity"],
                    "contract_number": row["contract_number"],
                    "sales_total": 0,
                    "payments_total": 0,
                },
            )
            entry["payments_total"] = row["payments_total"] or 0

        rows = []
        for entry in combined.values():
            sales_total = entry["sales_total"]
            payments_total = entry["payments_total"]
            rows.append(
                {
                    **entry,
                    "difference": sales_total - payments_total,
                    "payment_share": float(payments_total) / float(sales_total)
                    if sales_total
                    else None,
                }
            )
        rows.sort(key=lambda r: r["sales_total"], reverse=True)

        return Response({"rows": rows, "disclaimer": SALES_VS_PAYMENTS_DISCLAIMER})


class SaleRecordDetailView(APIView):
    def get(self, request, pk):
        try:
            record = SaleRecord.objects.select_related("organization", "import_batch").get(pk=pk)
        except SaleRecord.DoesNotExist:
            return Response({"detail": "Запись не найдена."}, status=404)

        return Response(
            {
                "id": record.id,
                "organization": record.organization.name,
                "sale_date": record.sale_date,
                "counterparty_raw": record.counterparty_raw,
                "legal_entity": record.legal_entity,
                "contract_number": record.contract_number,
                "nomenclature": record.nomenclature,
                "quantity": record.quantity,
                "amount": record.amount,
                "import_batch_id": record.import_batch_id,
                "source_file": record.source_file,
                "source_sheet": record.source_sheet,
                "source_row_number": record.source_row_number,
                "source_quantity_column": record.source_quantity_column,
                "source_amount_column": record.source_amount_column,
                "file_download_url": f"/api/imports/{record.import_batch_id}/file/",
            }
        )


class PaymentRecordDetailView(APIView):
    def get(self, request, pk):
        try:
            record = PaymentRecord.objects.select_related("organization", "import_batch").get(pk=pk)
        except PaymentRecord.DoesNotExist:
            return Response({"detail": "Запись не найдена."}, status=404)

        return Response(
            {
                "id": record.id,
                "organization": record.organization.name,
                "payment_date": record.payment_date,
                "counterparty_raw": record.counterparty_raw,
                "legal_entity": record.legal_entity,
                "contract_number": record.contract_number,
                "amount": record.amount,
                "import_batch_id": record.import_batch_id,
                "source_file": record.source_file,
                "source_sheet": record.source_sheet,
                "source_row_number": record.source_row_number,
                "file_download_url": f"/api/imports/{record.import_batch_id}/file/",
            }
        )
