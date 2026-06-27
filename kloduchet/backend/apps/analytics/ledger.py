"""Бухгалтерия: построчные регистры продаж/приходов/оплат с агрегирующими функциями."""

from django.db.models import Avg, Count, Max, Min, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.banking.models import BankTransaction
from apps.organizations.scoping import TestClientObfuscationMixin, scoped_organization_ids
from apps.payments.models import PaymentRecord
from apps.sales.models import SaleRecord

AGG_FUNCS = {
    "sum": Sum,
    "count": Count,
    "avg": Avg,
    "min": Min,
    "max": Max,
}

TRUNC_BY_GROUP = {
    "day": TruncDay,
    "week": TruncWeek,
    "month": TruncMonth,
}


class LedgerConfig:
    def __init__(self, model, date_field, fields, group_fields, amount_fields, default_agg_field):
        self.model = model
        self.date_field = date_field
        self.fields = fields
        self.group_fields = group_fields
        self.amount_fields = amount_fields
        self.default_agg_field = default_agg_field


SALES_CONFIG = LedgerConfig(
    model=SaleRecord,
    date_field="sale_date",
    fields=[
        "id",
        "organization__name",
        "sale_date",
        "counterparty_raw",
        "legal_entity",
        "nomenclature",
        "sales_doc_type",
        "sales_doc_number",
        "quantity",
        "amount",
    ],
    group_fields={
        "organization": "organization__name",
        "legal_entity": "legal_entity",
        "counterparty": "counterparty_raw",
        "nomenclature": "nomenclature",
        "doc_type": "sales_doc_type",
    },
    amount_fields=["amount", "quantity"],
    default_agg_field="amount",
)

RECEIPTS_CONFIG = LedgerConfig(
    model=BankTransaction,
    date_field="operation_date",
    fields=[
        "id",
        "organization__name",
        "operation_date",
        "counterparty_name",
        "document_number",
        "payment_purpose",
        "amount",
    ],
    group_fields={
        "organization": "organization__name",
        "counterparty": "counterparty_name",
    },
    amount_fields=["amount"],
    default_agg_field="amount",
)

PAYMENTS_CONFIG = LedgerConfig(
    model=PaymentRecord,
    date_field="payment_date",
    fields=[
        "id",
        "organization__name",
        "payment_date",
        "counterparty_raw",
        "legal_entity",
        "payment_doc_number",
        "amount",
    ],
    group_fields={
        "organization": "organization__name",
        "legal_entity": "legal_entity",
        "counterparty": "counterparty_raw",
    },
    amount_fields=["amount"],
    default_agg_field="amount",
)


def _filtered_queryset(config: LedgerConfig, request):
    qs = config.model.objects.filter(organization__is_active=True)
    if config.model is BankTransaction:
        qs = qs.filter(direction="credit")

    scoped = scoped_organization_ids(request)
    organizations = scoped if scoped is not None else request.query_params.getlist("organization")
    if organizations:
        qs = qs.filter(organization_id__in=organizations)

    date_from = request.query_params.get("date_from")
    date_to = request.query_params.get("date_to")
    if date_from:
        qs = qs.filter(**{f"{config.date_field}__gte": date_from})
    if date_to:
        qs = qs.filter(**{f"{config.date_field}__lte": date_to})

    counterparty = request.query_params.get("counterparty")
    if counterparty:
        counterparty_field = "counterparty_name" if config.model is BankTransaction else "counterparty_raw"
        qs = qs.filter(**{f"{counterparty_field}__icontains": counterparty})

    return qs


class LedgerView(TestClientObfuscationMixin, APIView):
    config: LedgerConfig

    def get(self, request):
        qs = _filtered_queryset(self.config, request).order_by(f"-{self.config.date_field}", "-id")

        try:
            page = max(int(request.query_params.get("page", 1)), 1)
            page_size = min(max(int(request.query_params.get("page_size", 50)), 1), 500)
        except ValueError:
            page, page_size = 1, 50

        total_count = qs.count()
        offset = (page - 1) * page_size
        rows = list(qs.values(*self.config.fields)[offset : offset + page_size])

        aggregation = self._aggregate(qs, request)

        return Response(
            {
                "rows": rows,
                "count": total_count,
                "page": page,
                "page_size": page_size,
                "groupable_fields": list(self.config.group_fields.keys()),
                "amount_fields": self.config.amount_fields,
                "aggregation": aggregation,
            }
        )

    def _aggregate(self, qs, request):
        agg_name = request.query_params.get("agg", "sum")
        agg_func = AGG_FUNCS.get(agg_name, Sum)
        agg_field = request.query_params.get("agg_field", self.config.default_agg_field)
        if agg_field not in self.config.amount_fields:
            agg_field = self.config.default_agg_field

        group_by = request.query_params.get("group_by")
        period = request.query_params.get("period")

        if period and period in TRUNC_BY_GROUP:
            trunc = TRUNC_BY_GROUP[period]
            grouped = (
                qs.annotate(group=trunc(self.config.date_field))
                .values("group")
                .annotate(value=agg_func(agg_field))
                .order_by("group")
            )
            results = [
                {"group": row["group"], "value": row["value"] or 0}
                for row in grouped
                if row["group"] is not None
            ]
        elif group_by and group_by in self.config.group_fields:
            db_field = self.config.group_fields[group_by]
            grouped = (
                qs.values(db_field).annotate(value=agg_func(agg_field)).order_by("-value")
            )
            results = [{"group": row[db_field], "value": row["value"] or 0} for row in grouped]
        else:
            total = qs.aggregate(value=agg_func(agg_field))["value"] or 0
            results = [{"group": None, "value": total}]

        return {
            "agg": agg_name if agg_name in AGG_FUNCS else "sum",
            "agg_field": agg_field,
            "group_by": group_by,
            "period": period,
            "results": results,
        }


class LedgerSalesView(LedgerView):
    config = SALES_CONFIG


class LedgerReceiptsView(LedgerView):
    config = RECEIPTS_CONFIG


class LedgerPaymentsView(LedgerView):
    config = PAYMENTS_CONFIG
