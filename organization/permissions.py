"""Règles d'accès aux données des employés (un employé n'accède jamais aux données d'un autre)."""
from accounts.permissions import is_rh


def can_view_employee(user, employee):
    """RH et Admin : tout le monde. Employé : sa propre fiche. Manager : sa fiche et celles de son équipe directe."""
    if is_rh(user) or getattr(user, "is_admin_role", False):
        return True
    me = user.employee_profile
    if me is None:
        return False
    if me.pk == employee.pk:
        return True
    return user.role == "MANAGER" and employee.manager_id == me.pk


def can_view_documents(user, employee):
    """Les pièces du dossier sont réservées au RH, à l'Admin et à l'employé concerné."""
    if is_rh(user) or getattr(user, "is_admin_role", False):
        return True
    me = user.employee_profile
    return me is not None and me.pk == employee.pk
