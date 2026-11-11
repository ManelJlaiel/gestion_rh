from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from leaves.models import Holiday, LeaveType
from organization.models import Department
from payroll.models import PayrollRate

User = get_user_model()


class BootstrapMixin:
    """Ajoute les classes Bootstrap à tous les champs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class LeaveTypeForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = LeaveType
        fields = ["name", "annual_days", "requires_justification"]


class HolidayForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Holiday
        fields = ["date", "name"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


class DepartmentForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class PayrollRateForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = PayrollRate
        fields = ["code", "label", "rate", "lower_bound", "upper_bound", "valid_from"]
        widgets = {"valid_from": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def clean(self):
        data = super().clean()
        low, high = data.get("lower_bound"), data.get("upper_bound")
        if low is not None and high is not None and high <= low:
            self.add_error("upper_bound", "La borne supérieure doit dépasser la borne inférieure.")
        return data


from django.db.models import Q


def save_user_department(user, role, department):
    """Associe le département à l'employé et synchronise sa fiche employé."""
    from decimal import Decimal
    from django.utils import timezone
    from organization.models import ContractType, Employee

    employee = user.employee_profile
    if not employee:
        employee = Employee.objects.create(
            user=user,
            first_name=user.first_name or user.username,
            last_name=user.last_name or "",
            email=user.email or f"{user.username}@demo.tn",
            job_title=f"Manager {department.name}" if (role == User.Role.MANAGER and department) else (
                "Manager" if role == User.Role.MANAGER else user.get_role_display()
            ),
            department=department,
            hire_date=timezone.localdate(),
            contract_type=ContractType.CDI,
            base_salary=Decimal("0.000"),
            is_active=user.is_active,
        )
    else:
        employee.first_name = user.first_name or employee.first_name
        employee.last_name = user.last_name or employee.last_name
        employee.email = user.email or employee.email
        employee.is_active = user.is_active
        employee.department = department
        if role == User.Role.MANAGER and department:
            employee.job_title = f"Manager {department.name}"
        elif role == User.Role.EMPLOYE and (not employee.job_title or employee.job_title.startswith("Manager")):
            employee.job_title = "Employé"
        employee.save()

    if role == User.Role.MANAGER and department:
        # Libérer les autres départements dirigés par cet employé
        Department.objects.filter(head=employee).exclude(pk=department.pk).update(head=None)
        # Assigner ce département
        department.head = employee
        department.save(update_fields=["head"])
    elif role != User.Role.MANAGER:
        # Si le rôle n'est plus MANAGER, libérer la direction de tout département (l'employé reste dans son département)
        Department.objects.filter(head=employee).update(head=None)


class DepartmentChoiceField(forms.ModelChoiceField):
    def __init__(self, *args, **kwargs):
        self.current_head = kwargs.pop("current_head", None)
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        if obj.head and obj.head != self.current_head:
            return f"{obj.name} (Déjà géré par {obj.head.full_name})"
        return obj.name


class UserCreateForm(BootstrapMixin, forms.ModelForm):
    username = forms.CharField(
        label="CIN",
        help_text="Numéro de carte d'identité nationale.",
        widget=forms.TextInput(attrs={"placeholder": "Ex: 09876543"}),
    )
    password = forms.CharField(label="Mot de passe initial", widget=forms.PasswordInput)
    department = DepartmentChoiceField(
        queryset=Department.objects.none(),
        required=False,
        label="Département",
        empty_label="— Aucun département —",
        help_text="Département d'affectation de l'employé.",
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "role", "department"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.select_related("head").order_by("name")
        occupied = list(Department.objects.filter(head__isnull=False).values_list("pk", flat=True))
        self.fields["department"].widget.attrs["data-occupied"] = ",".join(str(i) for i in occupied)

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        department = cleaned_data.get("department")
        if role == User.Role.MANAGER and department and department.head:
            self.add_error("department", f"Le département « {department.name} » a déjà un manager ({department.head.full_name}).")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            save_user_department(user, self.cleaned_data.get("role"), self.cleaned_data.get("department"))
        return user


class UserEditForm(BootstrapMixin, forms.ModelForm):
    username = forms.CharField(
        label="CIN",
        help_text="Numéro de carte d'identité nationale.",
        widget=forms.TextInput(attrs={"placeholder": "Ex: 09876543"}),
    )
    department = DepartmentChoiceField(
        queryset=Department.objects.none(),
        required=False,
        label="Département",
        empty_label="— Aucun département —",
        help_text="Département d'affectation de l'employé.",
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "role", "department"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        employee = getattr(self.instance, "employee_profile", None) if self.instance.pk else None
        self.fields["department"].current_head = employee
        self.fields["department"].queryset = Department.objects.select_related("head").order_by("name")
        if employee and employee.department_id:
            self.initial["department"] = employee.department_id

        occupied = list(Department.objects.filter(head__isnull=False).exclude(head=employee).values_list("pk", flat=True))
        self.fields["department"].widget.attrs["data-occupied"] = ",".join(str(i) for i in occupied)

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        department = cleaned_data.get("department")
        if role == User.Role.MANAGER and department and department.head:
            employee = getattr(self.instance, "employee_profile", None) if self.instance.pk else None
            if department.head != employee:
                self.add_error("department", f"Le département « {department.name} » a déjà un manager ({department.head.full_name}).")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            save_user_department(user, self.cleaned_data.get("role"), self.cleaned_data.get("department"))
        return user
