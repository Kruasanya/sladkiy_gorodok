from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import AuditEvent, Organization

User = get_user_model()


class OrganizationModelTests(TestCase):
    def test_organization_requires_no_inn_to_be_created(self):
        org = Organization.objects.create(name="ИП Тестовый")
        self.assertTrue(org.is_active)
        self.assertEqual(org.inn, "")


class OrganizationApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner", password="pass12345")
        self.client = APIClient()

    def test_anonymous_access_is_forbidden(self):
        response = self.client.get("/api/organizations/")
        self.assertEqual(response.status_code, 403)

    def test_create_organization_records_audit_event(self):
        self.client.force_authenticate(self.user)
        response = self.client.post("/api/organizations/", {"name": "ООО Ромашка"})
        self.assertEqual(response.status_code, 201)

        org_id = response.data["id"]
        events = AuditEvent.objects.filter(entity_type="Organization", entity_id=str(org_id))
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().action, "create")

    def test_update_organization_records_audit_event_with_old_and_new_values(self):
        self.client.force_authenticate(self.user)
        org = Organization.objects.create(name="ООО Старое имя")

        response = self.client.patch(f"/api/organizations/{org.id}/", {"name": "ООО Новое имя"})
        self.assertEqual(response.status_code, 200)

        event = AuditEvent.objects.filter(entity_type="Organization", action="update").latest("created_at")
        self.assertEqual(event.old_values["name"], "ООО Старое имя")
        self.assertEqual(event.new_values["name"], "ООО Новое имя")
