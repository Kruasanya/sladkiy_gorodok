from django.urls import path

from .views import (
    SalesCounterpartiesExportView,
    SalesProductsExportView,
    SalesTimelineExportView,
    SalesVsPaymentsExportView,
)

urlpatterns = [
    path("sales/timeline", SalesTimelineExportView.as_view(), name="export-sales-timeline"),
    path("sales/products", SalesProductsExportView.as_view(), name="export-sales-products"),
    path(
        "sales/counterparties",
        SalesCounterpartiesExportView.as_view(),
        name="export-sales-counterparties",
    ),
    path("sales-vs-payments", SalesVsPaymentsExportView.as_view(), name="export-sales-vs-payments"),
]
