from django.urls import path

from . import views

app_name = "organization"

urlpatterns = [
    # Employés
    path("employes/", views.employee_list, name="employee_list"),
    path("employes/ajouter/", views.employee_create, name="employee_create"),
    path("employes/export/", views.employee_export_csv, name="employee_export"),
    path("employes/<int:pk>/", views.employee_detail, name="employee_detail"),
    path("employes/<int:pk>/modifier/", views.employee_edit, name="employee_edit"),
    path("employes/<int:pk>/desactiver/", views.employee_deactivate, name="employee_deactivate"),
    # Contrats et documents d'un employé
    path("employes/<int:employee_pk>/contrats/ajouter/", views.contract_create, name="contract_create"),
    path("contrats/<int:pk>/modifier/", views.contract_edit, name="contract_edit"),
    path("employes/<int:employee_pk>/documents/ajouter/", views.document_upload, name="document_upload"),
    path("documents/<int:pk>/telecharger/", views.document_download, name="document_download"),
    path("documents/<int:pk>/supprimer/", views.document_delete, name="document_delete"),
    # Profil de l'utilisateur connecté
    path("profil/", views.my_profile, name="my_profile"),
    path("profil/modifier/", views.my_profile_edit, name="my_profile_edit"),
    # Départements
    path("departements/", views.department_list, name="department_list"),
    path("departements/ajouter/", views.department_create, name="department_create"),
    path("departements/<int:pk>/modifier/", views.department_edit, name="department_edit"),
    path("departements/<int:pk>/supprimer/", views.department_delete, name="department_delete"),
    # Organigramme (JSON)
    path("organigramme/", views.org_chart, name="org_chart"),
    path("api/organigramme/", views.org_chart_data, name="org_chart_data"),
    
]
