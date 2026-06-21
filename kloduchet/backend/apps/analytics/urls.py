from django.urls import path

from .views import (
    PaymentRecordDetailView,
    SaleRecordDetailView,
    SalesCounterpartiesView,
    SalesProductsView,
    SalesTimelineView,
    SalesVsPaymentsView,
)

urlpatterns = [
    path("sales/timeline", SalesTimelineView.as_view(), name="sales-timeline"),
    path("sales/products", SalesProductsView.as_view(), name="sales-products"),
    path("sales/counterparties", SalesCounterpartiesView.as_view(), name="sales-counterparties"),
    path("sales-vs-payments", SalesVsPaymentsView.as_view(), name="sales-vs-payments"),
    path("records/sales/<int:pk>", SaleRecordDetailView.as_view(), name="sale-record-detail"),
    path("records/payments/<int:pk>", PaymentRecordDetailView.as_view(), name="payment-record-detail"),
]
