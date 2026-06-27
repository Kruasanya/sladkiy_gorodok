from rest_framework import serializers

from .models import ProductReference


class ProductReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductReference
        fields = [
            "id",
            "nomenclature_raw",
            "display_name",
            "is_active",
            "shelf_life_days",
            "unit_cost",
            "first_sale_date",
            "last_sale_date",
            "comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["nomenclature_raw", "first_sale_date", "last_sale_date", "created_at", "updated_at"]
