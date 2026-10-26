from django import forms
from django.contrib.auth.forms import PasswordChangeForm


class BootstrapMixin:
    """Ajoute les classes Bootstrap à tous les champs d'un formulaire."""

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


class StyledPasswordChangeForm(BootstrapMixin, PasswordChangeForm):
    """Changement de mot de passe (EF-AUT-04) avec le style Bootstrap du projet."""