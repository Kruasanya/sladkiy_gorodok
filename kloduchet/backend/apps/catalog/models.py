from django.db import models


class ProductReference(models.Model):
    nomenclature_raw = models.CharField(max_length=255, unique=True)
    display_name = models.CharField("общее название", max_length=255, blank=True)
    is_active = models.BooleanField("актуальность", default=True)
    shelf_life_days = models.IntegerField("срок годности, дней", null=True, blank=True)
    unit_cost = models.DecimalField(
        "себестоимость за единицу", max_digits=18, decimal_places=2, null=True, blank=True
    )
    first_sale_date = models.DateField(null=True, blank=True)
    last_sale_date = models.DateField(null=True, blank=True)
    comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name", "nomenclature_raw"]

    def __str__(self):
        return self.display_name or self.nomenclature_raw
