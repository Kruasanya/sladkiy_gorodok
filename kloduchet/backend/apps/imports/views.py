from pathlib import Path

from django.http import FileResponse, Http404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.organizations.models import Organization

from . import services
from .models import ImportBatch
from .serializers import ImportBatchSerializer, ImportUploadSerializer


class ImportBatchViewSet(viewsets.ModelViewSet):
    queryset = ImportBatch.objects.select_related("organization", "stored_file").all()
    serializer_class = ImportBatchSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        organization = self.request.query_params.get("organization")
        if organization:
            qs = qs.filter(organization_id=organization)
        return qs

    def create(self, request, *args, **kwargs):
        upload_serializer = ImportUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)
        data = upload_serializer.validated_data

        extension = Path(data["file"].name).suffix.lower()
        expected_extension = services.EXTENSION_BY_DATA_TYPE.get(data["data_type"])
        if extension not in services.ALLOWED_EXTENSIONS or extension != expected_extension:
            return Response(
                {
                    "detail": (
                        f"Недопустимое расширение файла: {extension}. "
                        f"Для типа «{data['data_type']}» ожидается {expected_extension}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            organization = Organization.objects.get(pk=data["organization"])
        except Organization.DoesNotExist:
            return Response({"detail": "Организация не найдена."}, status=status.HTTP_400_BAD_REQUEST)

        stored_file = services.save_uploaded_file(data["file"])
        batch = services.create_import_batch(
            organization=organization,
            data_type=data["data_type"],
            stored_file=stored_file,
            user=request.user,
        )
        batch = services.dispatch_import(batch)

        serializer = self.get_serializer(batch)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        batch = self.get_object()
        batch = services.dispatch_import(batch)
        return Response(self.get_serializer(batch).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        batch = self.get_object()
        try:
            batch = services.cancel_import(batch)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(batch).data)

    @action(detail=True, methods=["get"])
    def file(self, request, pk=None):
        batch = self.get_object()
        path = Path(batch.stored_file.storage_path)
        if not path.exists():
            raise Http404("Файл не найден на диске.")
        return FileResponse(
            open(path, "rb"),
            as_attachment=True,
            filename=batch.original_filename,
        )
