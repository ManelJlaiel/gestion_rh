from django.db import models


class Department(models.Model):
    """Responsable : Eya Ben Youssef."""

    name = models.CharField("nom", max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "département"

    def __str__(self):
        return self.name
