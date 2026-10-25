from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from audit.models import AuditLog, log_action


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    log_action(user, AuditLog.Action.LOGIN, user, f"Connexion : {user.username}")


@receiver(user_login_failed)
def log_login_failed(sender, credentials, request=None, **kwargs):
    """Trace les échecs de connexion (aide à repérer une tentative d'intrusion)."""
    username = credentials.get("username", "") if credentials else ""
    log_action(None, AuditLog.Action.LOGIN, None, f"Échec de connexion : {username}")