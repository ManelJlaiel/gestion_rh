from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts.views import PasswordChangeView, RateLimitedLoginView, home

urlpatterns = [
    path("", home, name="home"),
    path("connexion/", RateLimitedLoginView.as_view(), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
    path("mot-de-passe/", PasswordChangeView.as_view(), name="password_change"),
    path("organisation/", include("organization.urls")),
    path("administration/", include("administration.urls")),
    path("django-admin/", admin.site.urls),
]
