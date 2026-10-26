from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from audit.models import AuditLog, log_action

from .forms import StyledPasswordChangeForm


@login_required
def home(request):
    """Redirige chaque utilisateur vers l'espace de son rôle."""
    if request.user.is_admin_role:
        return redirect("administration:dashboard")
    if request.user.is_rh:
        return redirect("organization:employee_list")
        # Espace Employé / Manager : résumé de la fiche, actions rapides, équipe du manager.
    # Les autres modules (congés, présences, paie) ajouteront leurs tuiles dans home.html.
    employee = request.user.employee_profile
    team = []
    if employee is not None and request.user.role == request.user.Role.MANAGER:
        team = employee.subordinates.filter(is_active=True).select_related("department")
    context = {
        "employee": employee,
        "team": team,
        "documents_count": employee.documents.count() if employee is not None else 0,
    }
    return render(request, "home.html", context)


class RateLimitedLoginView(auth_views.LoginView):
    """Connexion avec limitation de débit (cahier des charges, § 10).

    Après LOGIN_MAX_ATTEMPTS échecs pour un même couple (identifiant, adresse IP),
    la connexion est refusée pendant LOGIN_LOCKOUT_SECONDS secondes.
    """

    template_name = "registration/login.html"

    def _cache_key(self):
        username = self.request.POST.get("username", "").strip().lower()
        ip = self.request.META.get("REMOTE_ADDR", "")
        return f"login-failures:{username}:{ip}"

    def post(self, request, *args, **kwargs):
        if cache.get(self._cache_key(), 0) >= settings.LOGIN_MAX_ATTEMPTS:
            form = self.get_form()
            form.add_error(None, "Trop de tentatives de connexion. Réessayez dans quelques minutes.")
            response = self.render_to_response(self.get_context_data(form=form))
            response.status_code = 429
            return response
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        key = self._cache_key()
        cache.add(key, 0, settings.LOGIN_LOCKOUT_SECONDS)  # crée le compteur s'il n'existe pas
        try:
            cache.incr(key)
        except ValueError:  # le compteur a expiré entre-temps
            cache.set(key, 1, settings.LOGIN_LOCKOUT_SECONDS)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(self._cache_key())
        return super().form_valid(form)


class PasswordChangeView(auth_views.PasswordChangeView):
    """L'utilisateur modifie son propre mot de passe (EF-AUT-04)."""

    form_class = StyledPasswordChangeForm
    template_name = "registration/password_change_form.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request.user, AuditLog.Action.UPDATE, self.request.user, "Mot de passe modifié")
        messages.success(self.request, "Votre mot de passe a été modifié.")
        return response