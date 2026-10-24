from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts.views import home

urlpatterns = [
    path("", home, name="home"),
    path("connexion/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
    path("administration/", include("administration.urls")),
    path("django-admin/", admin.site.urls),
]
