from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Restreint une vue aux rôles donnés (le superuser passe toujours)."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            user = request.user
            if user.is_superuser or user.role in roles:
                return view(request, *args, **kwargs)
            raise PermissionDenied

        return wrapper

    return decorator


# Raccourcis prêts à l'emploi : @rh_only, @rh_or_admin, @manager_or_rh
rh_only = role_required("RH")
rh_or_admin = role_required("RH", "ADMIN")
manager_or_rh = role_required("MANAGER", "RH")


def is_rh(user):
    """Vrai pour le RH (et le superuser) : seul profil qui voit salaires et contrats."""
    return user.is_authenticated and (user.is_superuser or user.role == "RH")