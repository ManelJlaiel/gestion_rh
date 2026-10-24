from django.db import models


class PayrollRate(models.Model):
    """Taux de paie paramétrable (CNSS, tranches IRPP). Responsable : Manel Jlaiel.

    Les taux changent avec les lois de finances : on ne les code jamais en dur.
    Pour une tranche IRPP, ``lower_bound``/``upper_bound`` définissent la tranche
    de revenu annuel imposable.
    """

    class Code(models.TextChoices):
        CNSS = "CNSS", "Cotisation CNSS (part salariale)"
        IRPP = "IRPP", "Tranche IRPP"

    code = models.CharField(max_length=10, choices=Code.choices)
    label = models.CharField("libellé", max_length=100)
    rate = models.DecimalField("taux (%)", max_digits=5, decimal_places=2)
    lower_bound = models.DecimalField("borne inférieure", max_digits=12, decimal_places=3, null=True, blank=True)
    upper_bound = models.DecimalField("borne supérieure", max_digits=12, decimal_places=3, null=True, blank=True)
    valid_from = models.DateField("en vigueur depuis")

    class Meta:
        ordering = ["code", "lower_bound"]
        verbose_name = "taux de paie"
        verbose_name_plural = "taux de paie"

    def __str__(self):
        return f"{self.label} : {self.rate} %"
