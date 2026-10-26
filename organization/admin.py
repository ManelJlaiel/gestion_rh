from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Contract, Department, Document, Employee


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "head")


@admin.register(Employee)
class EmployeeAdmin(SimpleHistoryAdmin):
    list_display = ("matricule", "last_name", "first_name", "job_title", "department", "is_active")
    list_filter = ("department", "contract_type", "is_active")
    search_fields = ("matricule", "first_name", "last_name", "email")


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("employee", "contract_type", "start_date", "end_date", "status")
    list_filter = ("contract_type", "status")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "employee", "doc_type", "uploaded_at")
    list_filter = ("doc_type",)
