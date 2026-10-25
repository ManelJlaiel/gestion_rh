from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Utilisateur unique de l'application ; le rôle détermine les droits.

    Responsable : Eya Ben Youssef (socle). Ne pas modifier sans prévenir l'équipe.
    """

    class Role(models.TextChoices):
        EMPLOYE = "EMPLOYE", "Employé"
        MANAGER = "MANAGER", "Manager"
        RH = "RH", "RH"
        ADMIN = "ADMIN", "Administrateur"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.EMPLOYE)

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_rh(self):
        return self.role == self.Role.RH

    @property
    def employee_profile(self):
        """Fiche employé liée à ce compte, ou None (ex. : compte administrateur).

        Les autres modules doivent utiliser cette propriété plutôt que
        ``user.employee`` qui lève une exception quand la fiche n'existe pas.
        """
        return getattr(self, "employee", None)