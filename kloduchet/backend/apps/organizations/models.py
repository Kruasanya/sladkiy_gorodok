import uuid

from django.conf import settings
from django.db import models


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    inn = models.CharField(max_length=20, blank=True)
    kpp = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    is_test = models.BooleanField(
        default=False, help_text="Тестовая организация для демонстрационного доступа."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class UserProfile(models.Model):
    """Расширение пользователя Django: привязка к организации и признак тестового клиента.

    plaintext_password хранится отдельно от хеша исключительно для того, чтобы
    администратор мог посмотреть пароль пользователя в карточке (по явному
    решению — Django не позволяет восстановить пароль из хеша).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name="users"
    )
    is_test_client = models.BooleanField(default=False)
    plaintext_password = models.CharField(max_length=128, blank=True)

    def __str__(self) -> str:
        return f"Profile<{self.user.username}>"


class AuditEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=64)
    action = models.CharField(max_length=20)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
