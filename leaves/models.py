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


class LeaveRequest(models.Model):
    """Demande et enregistrement de congé d'un employé."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        APPROVED = "APPROVED", "Approuvé"
        REJECTED = "REJECTED", "Refusé"

    employee = models.ForeignKey(
        "organization.Employee",
        on_delete=models.CASCADE,
        related_name="leave_requests",
        verbose_name="employé",
    )
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.PROTECT,
        related_name="requests",
        verbose_name="type de congé",
    )
    start_date = models.DateField("date de début")
    end_date = models.DateField("date de fin")
    days_count = models.PositiveSmallIntegerField("nombre de jours", default=1)
    status = models.CharField(
        "statut",
        max_length=15,
        choices=Status.choices,
        default=Status.APPROVED,
    )
    reason = models.TextField("motif", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "demande de congé"

    def __str__(self):
        return f"{self.employee} — {self.leave_type} ({self.start_date} au {self.end_date})"
