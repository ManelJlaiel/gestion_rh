from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Le journal est en lecture seule : personne ne peut l'altérer, même depuis l'admin."""

    list_display = ("timestamp", "user", "action", "object_type", "object_id")
    list_filter = ("action",)
    search_fields = ("description", "user__username")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
