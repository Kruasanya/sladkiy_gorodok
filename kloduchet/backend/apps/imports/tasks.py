from celery import shared_task

from . import services
from .models import ImportBatch


@shared_task
def run_import_task(batch_id: str) -> None:
    batch = ImportBatch.objects.get(pk=batch_id)
    services.run_import(batch)
