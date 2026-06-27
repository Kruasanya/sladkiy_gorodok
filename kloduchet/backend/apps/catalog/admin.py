from django.contrib import admin

from .models import ProductReference


@admin.register(ProductReference)
class ProductReferenceAdmin(admin.ModelAdmin):
    list_display = ["display_name", "nomenclature_raw", "is_active", "shelf_life_days", "unit_cost"]
    list_filter = ["is_active"]
    search_fields = ["display_name", "nomenclature_raw"]
