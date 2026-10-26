"""Remplit la base avec une entreprise fictive : départements, employés, comptes, contrats.

Usage : python manage.py seed_employees

Sans danger si on la relance : les personnes déjà créées sont réutilisées.
Tous les comptes créés ont le mot de passe  Demo2026!
"""
import random
import unicodedata
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from organization.models import Contract, ContractType, Department, Employee

User = get_user_model()
PASSWORD = "Demo2026!"

FIRST_NAMES = [
    "Ahmed", "Mohamed", "Ali", "Sami", "Karim", "Omar", "Youssef", "Mehdi", "Walid", "Hichem",
    "Aymen", "Bilel", "Slim", "Nizar", "Anis", "Fares", "Rami", "Skander", "Amine", "Hamza",
    "Sarra", "Mariem", "Nour", "Ines", "Rim", "Amel", "Salma", "Emna", "Fatma", "Hajer",
    "Wafa", "Olfa", "Meriem", "Syrine", "Asma", "Lina", "Yasmine", "Chaima", "Dorra", "Nesrine",
]  # fmt: skip
LAST_NAMES = [
    "Trabelsi", "Ben Salah", "Gharbi", "Jlassi", "Mansouri", "Bouazizi", "Hamdi", "Zouari", "Chebbi", "Khelifi",
    "Maaloul", "Dridi", "Ayari", "Sassi", "Bejaoui", "Karray", "Mejri", "Nasri", "Ouerghi", "Tlili",
    "Haddad", "Ferchichi", "Saidi", "Belhaj", "Cherif", "Gharsallah", "Mrad", "Rekik", "Souissi", "Torkhani",
]  # fmt: skip
STREETS = ["Avenue Habib Bourguiba", "Rue de la Liberté", "Avenue de Carthage", "Rue d'Alger", "Avenue de Paris"]
CITIES = ["Tunis", "Ariana", "La Marsa", "Ben Arous", "Sousse", "Sfax", "Nabeul", "Bizerte"]

# nom du département -> (responsable, effectif, postes possibles, fourchette de salaire en DT)
DEPARTMENTS = {
    "Direction": ("Directeur général", 1, ["Assistante de direction"], (2500, 3500)),
    "Ressources humaines": ("Responsable RH", 4, ["Chargé de recrutement", "Gestionnaire de paie", "Assistant RH", "Chargé de formation"], (1800, 3000)),
    "Informatique": ("Directeur informatique", 9, ["Développeur backend", "Développeur frontend", "Ingénieur DevOps", "Data analyst", "Administrateur systèmes", "Testeur QA"], (2200, 4500)),
    "Production": ("Directeur de production", 13, ["Opérateur de production", "Technicien de maintenance", "Contrôleur qualité", "Magasinier"], (1100, 2200)),
    "Commercial": ("Directeur commercial", 8, ["Commercial terrain", "Assistant commercial", "Chargé de clientèle", "Responsable marketing"], (1500, 3200)),
    "Finance": ("Directeur financier", 5, ["Comptable", "Contrôleur de gestion", "Trésorier", "Assistant comptable"], (1800, 3500)),
}  # fmt: skip


def slug(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return text.lower().replace(" ", "").replace("'", "")


class Command(BaseCommand):
    help = "Crée une entreprise fictive complète (départements, hiérarchie, employés, comptes, contrats)."

    @transaction.atomic
    def handle(self, *args, **options):
        self.rng = random.Random(42)  # même résultat à chaque exécution
        self.name_rng = random.Random(7)  # générateur séparé : les noms restent identiques si on relance
        self.today = date.today()
        self.used_names = set()
        self.count = {"employees": 0, "users": 0, "contracts": 0}

        # Personnes réservées aux comptes de démonstration de seed_admin (rh, manager, employe).
        demo = {
            "Direction": ("Karim", "Ben Ali", "manager"),
            "Ressources humaines": ("Sonia", "Trabelsi", "rh"),
        }
        for first, last, _ in demo.values():
            self.used_names.add((first, last))
        self.used_names.add(("Yasmine", "Gharbi"))

        dg = None
        for dept_name, (head_title, size, jobs, salary_range) in DEPARTMENTS.items():
            dept, _ = Department.objects.get_or_create(name=dept_name)
            first, last, username = demo.get(dept_name, (None, None, None))
            role = User.Role.RH if dept_name == "Ressources humaines" else User.Role.MANAGER
            head = self.person(first, last, username, role, head_title, dept, dg, salary_range, senior=True)
            if dept_name == "Direction":
                dg = head
            dept.head = head
            dept.save()

            lead = None
            for i in range(size):
                job = jobs[i % len(jobs)]
                boss = head
                if size > 7 and i == 0:  # grands départements : un chef d'équipe intermédiaire
                    job = "Chef d'équipe" if dept_name == "Production" else "Lead développeur"
                elif size > 7 and lead is not None:
                    boss = lead
                username = "employe" if (dept_name == "Informatique" and i == 0) else None
                first, last = ("Yasmine", "Gharbi") if username else (None, None)
                person = self.person(first, last, username, User.Role.EMPLOYE, job, dept, boss, salary_range)
                if size > 7 and i == 0:
                    lead = person
                    person.user.role = User.Role.MANAGER  # le chef d'équipe est aussi manager
                    person.user.save(update_fields=["role"])

        self.deactivate_some()
        self.stdout.write(self.style.SUCCESS(
            f"Terminé : {self.count['employees']} employés, {self.count['users']} comptes, "
            f"{self.count['contracts']} contrats créés (total en base : {Employee.objects.count()} employés)."
        ))  # fmt: skip
        self.stdout.write(f"Mot de passe de tous les comptes : {PASSWORD}")
        self.stdout.write("Comptes utiles : admin, rh, manager, employe (+ prenom.nom pour les autres)")

    # ------------------------------------------------------------------ #
    def pick_name(self):
        while True:
            name = (self.name_rng.choice(FIRST_NAMES), self.name_rng.choice(LAST_NAMES))
            if name not in self.used_names:
                self.used_names.add(name)
                return name

    def person(self, first, last, username, role, job, dept, manager, salary_range, senior=False):
        if not first:
            first, last = self.pick_name()
        existing = Employee.objects.filter(first_name=first, last_name=last).first()
        if existing:
            return existing

        username = username or f"{slug(first)}.{slug(last)}"
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"first_name": first, "last_name": last, "email": f"{username}@demo.tn", "role": role},
        )
        if created:
            user.set_password(PASSWORD)
            user.save()
            self.count["users"] += 1
        elif hasattr(user, "employee"):
            return user.employee

        contract_type = ContractType.CDI if senior else self.rng.choices(
            [ContractType.CDI, ContractType.CDD, ContractType.SIVP, ContractType.STAGE], weights=[70, 15, 7, 8]
        )[0]  # fmt: skip
        if contract_type == ContractType.CDI:
            hire = date(2013, 1, 1) + timedelta(days=self.rng.randint(0, (date(2026, 6, 1) - date(2013, 1, 1)).days))
            end = None
        else:  # contrats à durée limitée : récents, donc encore en cours
            hire = self.today - timedelta(days=self.rng.randint(30, 300))
            end = hire + timedelta(days={"CDD": 540, "SIVP": 365, "STAGE": 180}[contract_type])
        low, high = salary_range
        if contract_type == ContractType.STAGE:
            low, high = 600, 900
        elif senior:
            low, high = int(high * 1.5), int(high * 2.2)
        salary = Decimal(self.rng.randrange(low, high + 1, 50))
        age = self.rng.randint(23, 55)
        birth = self.today - timedelta(days=age * 365 + self.rng.randint(0, 364))

        employee = Employee.objects.create(
            user=user, first_name=first, last_name=last, email=user.email,
            phone=f"{self.rng.choice('2459')}{self.rng.randint(1000000, 9999999)}",
            address=f"{self.rng.randint(1, 120)} {self.rng.choice(STREETS)}, {self.rng.choice(CITIES)}",
            birth_date=birth, job_title=job, department=dept, manager=manager,
            hire_date=hire, contract_type=contract_type, base_salary=salary,
        )  # fmt: skip
        Contract.objects.create(
            employee=employee, contract_type=contract_type, start_date=hire, end_date=end,
            salary=salary, status=Contract.Status.ACTIVE,
        )  # fmt: skip
        self.count["employees"] += 1
        self.count["contracts"] += 1
        return employee

    def deactivate_some(self):
        """Quelques anciens employés (pour tester le filtre « Inactifs » et la date de sortie)."""
        if Employee.objects.filter(is_active=False).exists():
            return  # déjà fait (ou désactivés à la main)
        leavers = Employee.objects.filter(is_active=True, subordinates__isnull=True, user__role=User.Role.EMPLOYE)
        leavers = leavers.exclude(user__username="employe").order_by("-pk")[:3]
        for employee in leavers:
            employee.is_active = False
            employee.exit_date = max(employee.hire_date, self.today - timedelta(days=self.rng.randint(10, 120)))
            employee.save()
            employee.contracts.update(status=Contract.Status.ENDED, end_date=employee.exit_date)
            if employee.user:
                employee.user.is_active = False
                employee.user.save(update_fields=["is_active"])