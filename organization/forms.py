from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from accounts.forms import BootstrapMixin

from .models import Contract, Department, Document, Employee

User = get_user_model()

DATE_WIDGET = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
MAX_UPLOAD_MB = 5


class DepartmentForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "description", "head"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["head"].queryset = Employee.objects.filter(is_active=True)


class EmployeeForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "first_name", "last_name", "email", "phone", "address", "birth_date",
            "job_title", "department", "manager", "hire_date", "contract_type", "base_salary",
            "user", "is_active", "exit_date",
        ]  # fmt: skip
        widgets = {
            "birth_date": DATE_WIDGET,
            "hire_date": DATE_WIDGET,
            "exit_date": DATE_WIDGET,
            "address": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Le manager doit être un autre employé actif.
        managers = Employee.objects.filter(is_active=True)
        if self.instance.pk:
            managers = managers.exclude(pk=self.instance.pk)
        self.fields["manager"].queryset = managers
        # Seuls les comptes qui n'ont pas encore de fiche (ou le compte actuel) sont proposés.
        free_users = Q(employee__isnull=True)
        if self.instance.pk and self.instance.user_id:
            free_users |= Q(pk=self.instance.user_id)
        self.fields["user"].queryset = User.objects.filter(free_users).order_by("username")


class EmployeeSelfForm(BootstrapMixin, forms.ModelForm):
    """Ce qu'un employé peut modifier lui-même (« Mettre à jour ses informations »)."""

    class Meta:
        model = Employee
        fields = ["phone", "address"]
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}


class ContractForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Contract
        fields = ["contract_type", "start_date", "end_date", "salary", "status"]
        widgets = {"start_date": DATE_WIDGET, "end_date": DATE_WIDGET}


class DocumentForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Document
        fields = ["doc_type", "title", "file"]

    def clean_file(self):
        file = self.cleaned_data["file"]
        if file.size > MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(f"Le fichier dépasse {MAX_UPLOAD_MB} Mo.")
        return file
