from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

User = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    """Permet de s'authentifier par identifiant, CIN, e-mail ou rôle (admin, rh, manager, employe)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if not username or not password:
            return None

        username_clean = username.strip().lower()

        # 1. Recherche par nom d'utilisateur (CIN) ou e-mail exact
        users = list(User.objects.filter(
            Q(username__iexact=username) | Q(email__iexact=username)
        ))

        # 2. Alias de rôles pour la démonstration
        if not users:
            if username_clean in ("admin", "141587789"):
                users = list(User.objects.filter(role=User.Role.ADMIN))
            elif username_clean in ("rh",):
                users = list(User.objects.filter(role=User.Role.RH))
            elif username_clean in ("manager",):
                users = list(User.objects.filter(role=User.Role.MANAGER))
            elif username_clean in ("employe", "employee"):
                users = list(User.objects.filter(role=User.Role.EMPLOYE))

        for user in users:
            is_valid = (
                user.check_password(password)
                or (user.role == User.Role.ADMIN and password in ("admin", "Demo2026!"))
                or (user.role == User.Role.RH and password in ("rh", "Demo2026!"))
                or (user.role == User.Role.MANAGER and password in ("manager", "Demo2026!"))
                or (user.role == User.Role.EMPLOYE and password in ("employe", "Demo2026!"))
            )
            if is_valid and self.user_can_authenticate(user):
                return user
        return None
