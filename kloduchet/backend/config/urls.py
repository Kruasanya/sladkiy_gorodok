from django.contrib import admin
from django.urls import include, path

from apps.organizations.urls import urlpatterns_users

from .auth_views import LoginView, LogoutView, MeView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/login", LoginView.as_view(), name="auth-login"),
    path("api/auth/logout", LogoutView.as_view(), name="auth-logout"),
    path("api/auth/me", MeView.as_view(), name="auth-me"),
    path("api/organizations/", include("apps.organizations.urls")),
    path("api/users/", include(urlpatterns_users)),
    path("api/imports/", include("apps.imports.urls")),
    path("api/analytics/", include("apps.analytics.urls")),
    path("api/exports/", include("apps.exports.urls")),
    path("api/catalog/", include("apps.catalog.urls")),
]
