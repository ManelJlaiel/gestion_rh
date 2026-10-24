from django.db import models


class LeaveType(models.Model):
    """Responsable : Eya Kouki."""

    name = models.CharField("nom", max_length=100, unique=True)
    annual_days = models.PositiveSmallIntegerField("jours par an", default=0)
    requires_justification = models.BooleanField("justificatif obligatoire", default=False)

    class Meta:
        ordering = ["name"]
        verbose_name = "type de congé"

    def __str__(self):
        return self.name


class Holiday(models.Model):
    """Jour férié. Responsable : Eya Kouki."""

    date = models.DateField(unique=True)
    name = models.CharField("nom", max_length=100)

    class Meta:
        ordering = ["date"]
        verbose_name = "jour férié"

    def __str__(self):
        return f"{self.name} ({self.date:%d/%m/%Y})"
