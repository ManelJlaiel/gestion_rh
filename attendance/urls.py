from django.urls import path
from . import views

app_name = "attendance"

urlpatterns = [
    path("", views.attendance_dashboard, name="dashboard"),
    path("pointer/", views.mark_attendance, name="mark"),
    path("conges/ajouter/", views.add_leave, name="add_leave"),
]
