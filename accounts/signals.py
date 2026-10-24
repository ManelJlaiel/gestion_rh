from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from audit.models import AuditLog, log_action


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    log_action(user, AuditLog.Action.LOGIN, user, f"Connexion : {user.username}")
