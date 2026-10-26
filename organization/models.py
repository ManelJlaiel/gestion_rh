import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.db.models import Max
from django.utils import timezone
from simple_history.models import HistoricalRecords


class ContractType(models.TextChoices):
    CDI = "CDI", "CDI"
    CDD = "CDD", "CDD"
    SIVP = "SIVP", "SIVP"
    STAGE = "STAGE", "Stage"


class Department(models.Model):
    """Responsable : Eya Ben Youssef."""

    name = models.CharField("nom", max_length=100, unique=True)
    description = models.TextField(blank=True)
    head = models.ForeignKey(
        "organization.Employee",
        verbose_name="responsable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="headed_departments",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "département"

    def __str__(self):
        return self.name


class Employee(models.Model):
    """Fiche employé (EF-EMP-01). Responsable : Eya Ben Youssef.

    Le compte ``user`` est facultatif : un employé peut exister avant d'avoir un compte.
    Les modifications (poste, salaire…) sont historisées par django-simple-history.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="compte utilisateur",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employee",
    )
    matricule = models.CharField(max_length=20, unique=True, editable=False, blank=True)
    first_name = models.CharField("prénom", max_length=100)
    last_name = models.CharField("nom", max_length=100)
    email = models.EmailField("e-mail", blank=True)
    phone = models.CharField("téléphone", max_length=20, blank=True)
    address = models.TextField("adresse", blank=True)
    birth_date = models.DateField("date de naissance", null=True, blank=True)

    job_title = models.CharField("poste", max_length=100)
    department = models.ForeignKey(
        Department,
        verbose_name="département",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employees",
    )
    manager = models.ForeignKey(
        "self",
        verbose_name="manager",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subordinates",
    )
    hire_date = models.DateField("date d'embauche")
    contract_type = models.CharField("type de contrat", max_length=10, choices=ContractType.choices, default=ContractType.CDI)
    base_salary = models.DecimalField(
        "salaire de base (DT)", max_digits=10, decimal_places=3, validators=[MinValueValidator(0)]
    )
    is_active = models.BooleanField("actif", default=True)
    exit_date = models.DateField("date de sortie", null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = "employé"

    def __str__(self):
        return f"{self.full_name} ({self.matricule})" if self.matricule else self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def clean(self):
        errors = {}
        if self.hire_date and self.exit_date and self.exit_date < self.hire_date:
            errors["exit_date"] = "La date de sortie ne peut pas précéder la date d'embauche."
        if self.manager_id and self.pk:
            # On remonte la chaîne hiérarchique : un employé ne peut pas être son propre supérieur.
            boss, seen = self.manager, set()
            while boss is not None and boss.pk not in seen:
                if boss.pk == self.pk:
                    errors["manager"] = "Ce choix créerait une boucle dans la hiérarchie."
                    break
                seen.add(boss.pk)
                boss = boss.manager
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.matricule:
            number = (Employee.objects.aggregate(m=Max("pk"))["m"] or 0) + 1
            while Employee.objects.filter(matricule=f"EMP-{number:04d}").exists():
                number += 1
            self.matricule = f"EMP-{number:04d}"
        super().save(*args, **kwargs)

    def deactivate(self):
        """Désactive l'employé en conservant sa date de sortie (EF-EMP-02)."""
        self.is_active = False
        if not self.exit_date:
            self.exit_date = timezone.localdate()
        self.save()


class Contract(models.Model):
    """Contrat de travail d'un employé. Responsable : Eya Ben Youssef."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIF", "En cours"
        ENDED = "TERMINE", "Terminé"

    employee = models.ForeignKey(Employee, verbose_name="employé", on_delete=models.CASCADE, related_name="contracts")
    contract_type = models.CharField("type", max_length=10, choices=ContractType.choices)
    start_date = models.DateField("date de début")
    end_date = models.DateField("date de fin", null=True, blank=True)
    salary = models.DecimalField("salaire (DT)", max_digits=10, decimal_places=3, validators=[MinValueValidator(0)])
    status = models.CharField("statut", max_length=10, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "contrat"

    def __str__(self):
        return f"{self.get_contract_type_display()} — {self.employee.full_name} ({self.start_date:%d/%m/%Y})"

    def clean(self):
        errors = {}
        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors["end_date"] = "La date de fin ne peut pas précéder la date de début."
        if self.contract_type in (ContractType.CDD, ContractType.SIVP, ContractType.STAGE) and not self.end_date:
            errors["end_date"] = "Une date de fin est obligatoire pour ce type de contrat."
        if errors:
            raise ValidationError(errors)


def document_path(instance, filename):
    return f"documents/employee_{instance.employee_id}/{filename}"


class Document(models.Model):
    """Pièce du dossier (contrat, CIN, diplôme…). Responsable : Eya Ben Youssef."""

    class DocType(models.TextChoices):
        CONTRACT = "CONTRAT", "Contrat"
        CIN = "CIN", "CIN"
        DIPLOMA = "DIPLOME", "Diplôme"
        OTHER = "AUTRE", "Autre"

    employee = models.ForeignKey(Employee, verbose_name="employé", on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField("type", max_length=10, choices=DocType.choices, default=DocType.OTHER)
    title = models.CharField("titre", max_length=150)
    file = models.FileField(
        "fichier",
        upload_to=document_path,
        validators=[FileExtensionValidator(["pdf", "png", "jpg", "jpeg", "doc", "docx"])],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "document"

    def __str__(self):
        return self.title

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    def delete(self, *args, **kwargs):
        self.file.delete(save=False)  # supprime aussi le fichier sur le disque
        return super().delete(*args, **kwargs)
