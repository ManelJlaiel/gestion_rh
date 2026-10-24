from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "action", "object_type", "object_id")
    list_filter = ("action",)
    def has_change_permission(self, request, obj=None):
        return False
