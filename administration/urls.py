from django.urls import path

from . import views

app_name = "administration"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("parametres/", views.settings_view, name="settings_home"),
    path("parametres/<slug:section>/", views.settings_view, name="settings"),
    path("parametres/<slug:section>/ajouter/", views.settings_form, name="settings_add"),
    path("parametres/<slug:section>/<int:pk>/modifier/", views.settings_form, name="settings_edit"),
    path("parametres/<slug:section>/<int:pk>/supprimer/", views.settings_delete, name="settings_delete"),
    path("comptes/", views.users_list, name="users"),
    path("comptes/ajouter/", views.user_create, name="user_add"),
    path("comptes/<int:pk>/modifier/", views.user_edit, name="user_edit"),
    path("comptes/<int:pk>/activer/", views.user_toggle_active, name="user_toggle"),
    path("comptes/<int:pk>/reinitialiser/", views.user_reset_password, name="user_reset"),
    path("audit/", views.audit_list, name="audit"),
]
