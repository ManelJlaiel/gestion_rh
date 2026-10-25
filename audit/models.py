from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Trace qui a consulté ou modifié quoi.

    Responsable du mécanisme d'enregistrement : Eya Ben Youssef.
    Page de consultation : Manel Jlaiel.
    """

    class Action(models.TextChoices):
        READ = "READ", "Consultation"
        CREATE = "CREATE", "Création"
        UPDATE = "UPDATE", "Modification"
        DELETE = "DELETE", "Suppression"
        LOGIN = "LOGIN", "Connexion"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="audit_logs")
    action = models.CharField(max_length=10, choices=Action.choices)
    object_type = models.CharField("type d'objet", max_length=100)
    object_id = models.CharField(max_length=64, blank=True)
    description = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "entrée d'audit"

    def __str__(self):
        return f"{self.timestamp:%d/%m/%Y %H:%M} {self.user} {self.action} {self.object_type}"


def log_action(user, action, obj=None, description=""):
    """Raccourci pour enregistrer une action depuis une vue.

    ``user`` peut être None ou anonyme (ex. : échec de connexion) ; ``obj`` est
    facultatif (ex. : export global). La description est tronquée à 255 caractères.
    Ne jamais y mettre de donnée sensible (salaire, mot de passe).
    """
    return AuditLog.objects.create(
        user=user if user and user.is_authenticated else None,
        action=action,
        object_type=obj._meta.verbose_name if obj is not None else "",
        object_id=str(obj.pk) if obj is not None else "",
        description=description[:255],
    )


def log_read(user, obj, description=""):
    """Enregistre la consultation d'un objet sensible (fiche employé, document…)."""
    return log_action(user, AuditLog.Action.READ, obj, description or f"Consultation : {obj}")


def changed_fields(form):
    """Noms (lisibles) des champs modifiés d'un formulaire, sans leurs valeurs.

    Permet de journaliser « quoi » a changé sans écrire de données sensibles.
    """
    return ", ".join(str(form.fields[name].label or name) for name in form.changed_data)
