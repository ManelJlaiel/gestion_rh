"""Données de démonstration pour l'espace administrateur.

Usage : python manage.py seed_admin
Le seed complet (employés, congés, présences…) sera écrit par Ghada.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from leaves.models import Holiday, LeaveType
from organization.models import Department
from payroll.models import PayrollRate

User = get_user_model()

DEMO_PASSWORD = "Demo2026!"

USERS = [
    ("admin", "Admin", "Système", User.Role.ADMIN),
    ("rh", "Sonia", "Trabelsi", User.Role.RH),
    ("manager", "Karim", "Ben Ali", User.Role.MANAGER),
    ("employe", "Yasmine", "Gharbi", User.Role.EMPLOYE),
]

LEAVE_TYPES = [
    ("Congé annuel", 30, False),
    ("Congé maladie", 0, True),
    ("Congé sans solde", 0, False),
    ("Congé maternité", 30, True),
]

DEPARTMENTS = ["Direction", "Ressources humaines", "Informatique", "Production", "Commercial", "Finance"]

# Jours fériés civils (dates fixes). Les fêtes religieuses varient chaque année :
# à ajouter par l'administrateur.
FIXED_HOLIDAYS = [
    (1, 1, "Jour de l'an"),
    (3, 20, "Fête de l'indépendance"),
    (4, 9, "Journée des martyrs"),
    (5, 1, "Fête du travail"),
    (7, 25, "Fête de la République"),
    (8, 13, "Fête de la femme"),
    (10, 15, "Fête de l'évacuation"),
    (12, 17, "Fête de la révolution"),
]

# Valeurs indicatives : À VÉRIFIER avec la loi de finances en vigueur avant la démo.
CNSS_RATE = Decimal("9.18")
IRPP_BRACKETS = [
    (0, 5000, "0"),
    (5000, 10000, "15"),
    (10000, 20000, "25"),
    (20000, 30000, "30"),
    (30000, 40000, "33"),
    (40000, 50000, "36"),
    (50000, 70000, "38"),
    (70000, None, "40"),
]


class Command(BaseCommand):
    help = "Crée les comptes de démonstration et les paramètres de base."

    def handle(self, *args, **options):
        for username, first, last, role in USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": first, "last_name": last, "role": role, "email": f"{username}@demo.tn"},
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                if role == User.Role.ADMIN:
                    user.is_staff = user.is_superuser = True
                user.save()

        for name, days, justif in LEAVE_TYPES:
            LeaveType.objects.get_or_create(name=name, defaults={"annual_days": days, "requires_justification": justif})

        for name in DEPARTMENTS:
            Department.objects.get_or_create(name=name)

        year = date.today().year
        for y in (year, year + 1):
            for month, day, name in FIXED_HOLIDAYS:
                Holiday.objects.get_or_create(date=date(y, month, day), defaults={"name": name})

        start = date(year, 1, 1)
        PayrollRate.objects.get_or_create(
            code=PayrollRate.Code.CNSS,
            label="CNSS part salariale",
            defaults={"rate": CNSS_RATE, "valid_from": start},
        )
        for low, high, rate in IRPP_BRACKETS:
            label = f"IRPP {low:,} – {high:,} DT".replace(",", " ") if high else f"IRPP plus de {low:,} DT".replace(",", " ")
            PayrollRate.objects.get_or_create(
                code=PayrollRate.Code.IRPP,
                lower_bound=low,
                defaults={"label": label, "rate": Decimal(rate), "upper_bound": high, "valid_from": start},
            )

        self.stdout.write(self.style.SUCCESS(f"Données créées. Comptes : admin, rh, manager, employe — mot de passe : {DEMO_PASSWORD}"))
