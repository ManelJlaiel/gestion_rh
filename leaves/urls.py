from django.urls import path
from . import views

app_name = "leaves"

urlpatterns = [
    path("", views.leave_list, name="leave_list"),
    path("ajouter/", views.leave_create, name="leave_create"),
    path("<int:pk>/approuver/", views.leave_approve, name="leave_approve"),
    path("<int:pk>/refuser/", views.leave_reject, name="leave_reject"),
]

