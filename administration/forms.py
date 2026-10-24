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


class UserCreateForm(BootstrapMixin, forms.ModelForm):
    password = forms.CharField(label="Mot de passe initial", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "role"]

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class UserEditForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "role"]
