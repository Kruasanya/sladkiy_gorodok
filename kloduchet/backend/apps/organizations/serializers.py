from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from rest_framework import serializers

from .models import Organization, UserProfile

User = get_user_model()


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "legal_name",
            "inn",
            "kpp",
            "is_active",
            "is_test",
            "created_at",
            "updated_at",
        ]


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    plaintext_password = serializers.CharField(source="profile.plaintext_password", read_only=True)
    organization = serializers.PrimaryKeyRelatedField(
        source="profile.organization",
        queryset=Organization.objects.all(),
        required=False,
        allow_null=True,
    )
    organization_name = serializers.CharField(source="profile.organization.name", read_only=True, default=None)
    is_test_client = serializers.BooleanField(source="profile.is_test_client", required=False)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "plaintext_password",
            "is_staff",
            "is_active",
            "organization",
            "organization_name",
            "is_test_client",
            "date_joined",
            "last_login",
        ]
        read_only_fields = ["date_joined", "last_login"]

    def _extract_profile(self, validated_data):
        return validated_data.pop("profile", {})

    def create(self, validated_data):
        profile_data = self._extract_profile(validated_data)
        password = validated_data.pop("password", "") or User.objects.make_random_password()
        user = User(**validated_data)
        user.password = make_password(password)
        user.save()
        UserProfile.objects.create(
            user=user,
            plaintext_password=password,
            organization=profile_data.get("organization"),
            is_test_client=profile_data.get("is_test_client", False),
        )
        return user

    def update(self, instance, validated_data):
        profile_data = self._extract_profile(validated_data)
        password = validated_data.pop("password", "")
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()

        profile, _ = UserProfile.objects.get_or_create(user=instance)
        if password:
            profile.plaintext_password = password
        if "organization" in profile_data:
            profile.organization = profile_data["organization"]
        if "is_test_client" in profile_data:
            profile.is_test_client = profile_data["is_test_client"]
        profile.save()
        return instance
