import csv
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.catalog.models import ProductReference

DEFAULT_PATH = Path(settings.BASE_DIR).parent / "data" / "catalog" / "product_reference.csv"


def _parse_date(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    return date.fromisoformat(value)


def _parse_int(value: str) -> int | None:
    value = (value or "").strip()
    return int(value) if value else None


def _parse_decimal(value: str) -> str | None:
    value = (value or "").strip()
    return value or None


class Command(BaseCommand):
    help = "Импортирует/обновляет справочник товаров (общее название, актуальность и т.п.) из CSV."

    def add_arguments(self, parser):
        parser.add_argument("--path", default=str(DEFAULT_PATH))

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"Файл не найден: {path}"))
            return

        created, updated = 0, 0
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                nomenclature_raw = row["nomenclature_raw"].strip()
                defaults = {
                    "display_name": row.get("общее_название", "").strip(),
                    "is_active": row.get("актуальность", "").strip().lower() == "да",
                    "shelf_life_days": _parse_int(row.get("срок_годности_дней", "")),
                    "unit_cost": _parse_decimal(row.get("себестоимость_за_единицу", "")),
                    "first_sale_date": _parse_date(row.get("первая_продажа", "")),
                    "last_sale_date": _parse_date(row.get("последняя_продажа", "")),
                    "comment": row.get("комментарий", "").strip(),
                }
                _, was_created = ProductReference.objects.update_or_create(
                    nomenclature_raw=nomenclature_raw, defaults=defaults
                )
                created += was_created
                updated += not was_created

        self.stdout.write(self.style.SUCCESS(f"Создано: {created}, обновлено: {updated}"))
