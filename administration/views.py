import secrets
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import role_required
from audit.models import AuditLog, log_action
from leaves.models import Holiday, LeaveType
from organization.models import Department
from payroll.models import PayrollRate

from .forms import (
    DepartmentForm,
    HolidayForm,
    LeaveTypeForm,
    PayrollRateForm,
    UserCreateForm,
    UserEditForm,
)

User = get_user_model()
admin_only = role_required(User.Role.ADMIN)

# Une entrée par onglet de la page Paramètres : modèle, formulaire, colonnes affichées.
SETTINGS_SECTIONS = {
    "types-conges": {
        "label": "Types de congés",
        "icon": "bi-calendar2-week",
        "model": LeaveType,
        "form": LeaveTypeForm,
        "columns": [("name", "Nom"), ("annual_days", "Jours / an"), ("requires_justification", "Justificatif")],
    },
    "jours-feries": {
        "label": "Jours fériés",
        "icon": "bi-calendar-event",
        "model": Holiday,
        "form": HolidayForm,
        "columns": [("date", "Date"), ("name", "Nom")],
    },
    "departements": {
        "label": "Départements",
        "icon": "bi-diagram-3",
        "model": Department,
        "form": DepartmentForm,
        "columns": [("name", "Nom"), ("description", "Description")],
    },
    "taux-paie": {
        "label": "Taux de paie",
        "icon": "bi-percent",
        "model": PayrollRate,
        "form": PayrollRateForm,
        "columns": [
            ("get_code_display", "Type"),
            ("label", "Libellé"),
            ("rate", "Taux (%)"),
            ("lower_bound", "De"),
            ("upper_bound", "À"),
            ("valid_from", "Depuis"),
        ],
    },
}


def _section(key):
    try:
        return SETTINGS_SECTIONS[key]
    except KeyError:
        raise Http404("Section inconnue")


# --------------------------------------------------------------------------- #
# Tableau de bord
# --------------------------------------------------------------------------- #
@admin_only
def dashboard(request):
    by_role = {row["role"]: row["n"] for row in User.objects.values("role").annotate(n=Count("id"))}
    week_ago = timezone.now() - timedelta(days=7)
    context = {
        "total_users": User.objects.count(),
        "inactive_users": User.objects.filter(is_active=False).count(),
        "roles": [(label, by_role.get(value, 0)) for value, label in User.Role.choices],
        "departments_count": Department.objects.count(),
        "leave_types_count": LeaveType.objects.count(),
        "upcoming_holidays": Holiday.objects.filter(date__gte=timezone.localdate())[:5],
        "recent_logs": AuditLog.objects.select_related("user")[:8],
        "actions_this_week": AuditLog.objects.filter(timestamp__gte=week_ago).count(),
    }
    return render(request, "administration/dashboard.html", context)


# --------------------------------------------------------------------------- #
# Paramètres (CRUD générique pour les 4 sections)
# --------------------------------------------------------------------------- #
@admin_only
def settings_view(request, section="types-conges"):
    conf = _section(section)
    objects = conf["model"].objects.all()
    rows = [(obj, [_value(obj, attr) for attr, _ in conf["columns"]]) for obj in objects]
    return render(
        request,
        "administration/settings.html",
        {"sections": SETTINGS_SECTIONS, "current": section, "conf": conf, "rows": rows},
    )


def _value(obj, attr):
    value = getattr(obj, attr)
    return value() if callable(value) else value


@admin_only
def settings_form(request, section, pk=None):
    conf = _section(section)
    instance = get_object_or_404(conf["model"], pk=pk) if pk else None
    form = conf["form"](request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        action = AuditLog.Action.UPDATE if instance else AuditLog.Action.CREATE
        log_action(request.user, action, obj, f"{conf['label']} : {obj}")
        messages.success(request, f"« {obj} » a été enregistré.")
        return redirect("administration:settings", section=section)
    return render(
        request,
        "administration/settings_form.html",
        {"sections": SETTINGS_SECTIONS, "current": section, "conf": conf, "form": form, "instance": instance},
    )


@admin_only
@require_POST
def settings_delete(request, section, pk):
    conf = _section(section)
    obj = get_object_or_404(conf["model"], pk=pk)
    name = str(obj)
    log_action(request.user, AuditLog.Action.DELETE, obj, f"{conf['label']} : {name}")
    obj.delete()
    messages.success(request, f"« {name} » a été supprimé.")
    return redirect("administration:settings", section=section)


# --------------------------------------------------------------------------- #
# Comptes utilisateurs
# --------------------------------------------------------------------------- #
@admin_only
def users_list(request):
    users = User.objects.order_by("username")
    q = request.GET.get("q", "").strip()
    role = request.GET.get("role", "")
    status = request.GET.get("status", "")
    if q:
        users = users.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
        )
    if role:
        users = users.filter(role=role)
    if status == "actif":
        users = users.filter(is_active=True)
    elif status == "inactif":
        users = users.filter(is_active=False)
    page = Paginator(users, 15).get_page(request.GET.get("page"))
    return render(
        request,
        "administration/users_list.html",
        {"page": page, "roles": User.Role.choices, "q": q, "role": role, "status": status},
    )


@admin_only
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        log_action(request.user, AuditLog.Action.CREATE, user, f"Compte créé : {user.username} ({user.role})")
        messages.success(request, f"Le compte « {user.username} » a été créé.")
        return redirect("administration:users")
    return render(request, "administration/user_form.html", {"form": form, "creating": True})


@admin_only
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    old_role = target.role
    form = UserEditForm(request.POST or None, instance=target)
    if request.method == "POST" and form.is_valid():
        if target == request.user and form.cleaned_data["role"] != User.Role.ADMIN and not target.is_superuser:
            form.add_error("role", "Vous ne pouvez pas retirer votre propre rôle d'administrateur.")
        else:
            user = form.save()
            detail = f"Compte modifié : {user.username}"
            if old_role != user.role:
                detail += f" (rôle {old_role} → {user.role})"
            log_action(request.user, AuditLog.Action.UPDATE, user, detail)
            messages.success(request, f"Le compte « {user.username} » a été mis à jour.")
            return redirect("administration:users")
    return render(request, "administration/user_form.html", {"form": form, "target": target, "creating": False})


@admin_only
@require_POST
def user_toggle_active(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target == request.user:
        messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
    else:
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
        state = "réactivé" if target.is_active else "désactivé"
        log_action(request.user, AuditLog.Action.UPDATE, target, f"Compte {state} : {target.username}")
        messages.success(request, f"Le compte « {target.username} » a été {state}.")
    if request.headers.get("HX-Request"):
        # Avec HTMX, on renvoie uniquement la ligne mise à jour.
        return render(request, "administration/partials/user_row.html", {"u": target})
    return redirect("administration:users")


@admin_only
@require_POST
def user_reset_password(request, pk):
    target = get_object_or_404(User, pk=pk)
    temp_password = secrets.token_urlsafe(9)
    target.set_password(temp_password)
    target.save(update_fields=["password"])
    log_action(request.user, AuditLog.Action.UPDATE, target, f"Mot de passe réinitialisé : {target.username}")
    # Le mot de passe temporaire n'est affiché qu'une seule fois.
    return render(request, "administration/password_reset_done.html", {"target": target, "temp_password": temp_password})


# --------------------------------------------------------------------------- #
# Journal d'audit (lecture seule)
# --------------------------------------------------------------------------- #
@admin_only
def audit_list(request):
    logs = AuditLog.objects.select_related("user")
    user_id = request.GET.get("user", "")
    action = request.GET.get("action", "")
    start = request.GET.get("start", "")
    end = request.GET.get("end", "")
    if user_id:
        logs = logs.filter(user_id=user_id)
    if action:
        logs = logs.filter(action=action)
    if start:
        logs = logs.filter(timestamp__date__gte=start)
    if end:
        logs = logs.filter(timestamp__date__lte=end)
    page = Paginator(logs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "administration/audit_list.html",
        {
            "page": page,
            "users": User.objects.order_by("username"),
            "actions": AuditLog.Action.choices,
            "f": {"user": user_id, "action": action, "start": start, "end": end},
        },
    )
