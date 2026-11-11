from django.db import models
from django.utils import timezone


class Attendance(models.Model):
    """Pointage quotidien d'un employé."""

    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Présent"
        LATE = "LATE", "En retard"
        ABSENT = "ABSENT", "Absent"

    employee = models.ForeignKey(
        "organization.Employee",
        on_delete=models.CASCADE,
        related_name="attendances",
        verbose_name="employé",
    )
    date = models.DateField("date", default=timezone.localdate)
    status = models.CharField(
        "statut",
        max_length=10,
        choices=Status.choices,
        default=Status.PRESENT,
    )
    check_in_time = models.TimeField("heure d'arrivée", null=True, blank=True)
    notes = models.CharField("remarques", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "employee__last_name"]
        unique_together = ("employee", "date")
        verbose_name = "pointage"

    def __str__(self):
        return f"{self.employee} — {self.date} : {self.get_status_display()}"
