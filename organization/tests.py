import json
import shutil
import tempfile
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from audit.models import AuditLog

from .models import Contract, Department, Document, Employee

User = get_user_model()
MEDIA = tempfile.mkdtemp()


def make_employee(first="Sami", last="Trabelsi", **kwargs):
    defaults = {"job_title": "Développeur", "hire_date": date(2024, 1, 15), "base_salary": Decimal("2500.000")}
    defaults.update(kwargs)
    return Employee.objects.create(first_name=first, last_name=last, **defaults)


class EmployeeModelTests(TestCase):
    def test_matricule_genere_automatiquement(self):
        a, b = make_employee("A", "A"), make_employee("B", "B")
        self.assertRegex(a.matricule, r"^EMP-\d{4}$")
        self.assertNotEqual(a.matricule, b.matricule)

    def test_matricule_ne_change_pas_a_la_modification(self):
        e = make_employee()
        before = e.matricule
        e.job_title = "Lead"
        e.save()
        self.assertEqual(e.matricule, before)

    def test_un_employe_ne_peut_pas_etre_son_propre_manager(self):
        e = make_employee()
        e.manager = e
        with self.assertRaises(ValidationError):
            e.full_clean()

    def test_boucle_hierarchique_interdite(self):
        boss = make_employee("Boss", "B")
        worker = make_employee("Worker", "W", manager=boss)
        boss.manager = worker
        with self.assertRaises(ValidationError):
            boss.full_clean()

    def test_date_de_sortie_apres_embauche(self):
        e = make_employee(exit_date=date(2020, 1, 1))
        with self.assertRaises(ValidationError):
            e.full_clean()

    def test_desactivation_conserve_la_date_de_sortie(self):
        e = make_employee()
        e.deactivate()
        e.refresh_from_db()
        self.assertFalse(e.is_active)
        self.assertIsNotNone(e.exit_date)

    def test_historique_poste_et_salaire(self):
        e = make_employee()
        e.job_title, e.base_salary = "Lead", Decimal("3200.000")
        e.save()
        self.assertEqual(e.history.count(), 2)
        self.assertEqual(e.history.last().base_salary, Decimal("2500.000"))

    def test_profil_employe_du_compte(self):
        user = User.objects.create_user("sami", password="x")
        self.assertIsNone(user.employee_profile)
        e = make_employee(user=user)
        self.assertEqual(user.employee_profile, e)


class ContractModelTests(TestCase):
    def test_cdd_exige_une_date_de_fin(self):
        c = Contract(employee=make_employee(), contract_type="CDD", start_date=date(2025, 1, 1), salary=1000)
        with self.assertRaises(ValidationError):
            c.full_clean()

    def test_cdi_sans_date_de_fin(self):
        c = Contract(employee=make_employee(), contract_type="CDI", start_date=date(2025, 1, 1), salary=1000)
        c.full_clean()  # ne lève rien


@override_settings(MEDIA_ROOT=MEDIA)
class OrganizationViewTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.rh = User.objects.create_user("rh", password="x", role=User.Role.RH)
        self.manager_user = User.objects.create_user("manager", password="x", role=User.Role.MANAGER)
        self.emp_user = User.objects.create_user("emp", password="x", role=User.Role.EMPLOYE)
        self.other_user = User.objects.create_user("other", password="x", role=User.Role.EMPLOYE)
        self.dept = Department.objects.create(name="IT")
        self.manager = make_employee("Karim", "Ben Ali", user=self.manager_user, department=self.dept, base_salary=4000)
        self.emp = make_employee("Yasmine", "Gharbi", user=self.emp_user, department=self.dept, manager=self.manager, base_salary=2100)
        self.other = make_employee("Omar", "Zouari", user=self.other_user, department=self.dept, base_salary=1900)

    # --- droits d'accès ------------------------------------------------- #
    def test_liste_reservee_au_rh(self):
        url = reverse("organization:employee_list")
        self.assertEqual(self.client.get(url).status_code, 302)
        for user in (self.emp_user, self.manager_user):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.rh)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_employe_ne_voit_pas_la_fiche_d_un_autre(self):
        self.client.force_login(self.emp_user)
        self.assertEqual(self.client.get(reverse("organization:employee_detail", args=[self.other.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("organization:employee_detail", args=[self.emp.pk])).status_code, 200)

    def test_manager_voit_son_equipe_seulement(self):
        self.client.force_login(self.manager_user)
        self.assertEqual(self.client.get(reverse("organization:employee_detail", args=[self.emp.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("organization:employee_detail", args=[self.other.pk])).status_code, 403)

    def test_salaire_visible_uniquement_par_le_rh(self):
        url = reverse("organization:employee_detail", args=[self.emp.pk])
        self.client.force_login(self.emp_user)
        self.assertNotContains(self.client.get(url), "Salaire de base")
        self.client.force_login(self.manager_user)
        self.assertNotContains(self.client.get(url), "Salaire de base")
        self.client.force_login(self.rh)
        self.assertContains(self.client.get(url), "Salaire de base")

    def test_consultation_journalisee(self):
        self.client.force_login(self.rh)
        self.client.get(reverse("organization:employee_detail", args=[self.emp.pk]))
        log = AuditLog.objects.filter(action=AuditLog.Action.READ, user=self.rh).first()
        self.assertEqual(log.object_id, str(self.emp.pk))

    # --- CRUD ------------------------------------------------------------ #
    def test_creation_d_un_employe(self):
        self.client.force_login(self.rh)
        resp = self.client.post(
            reverse("organization:employee_create"),
            {"first_name": "Nour", "last_name": "Hamdi", "job_title": "Comptable", "hire_date": "2025-03-01",
             "contract_type": "CDI", "base_salary": "1800", "is_active": "on", "department": self.dept.pk},
        )  # fmt: skip
        employee = Employee.objects.get(last_name="Hamdi")
        self.assertRedirects(resp, reverse("organization:employee_detail", args=[employee.pk]))
        self.assertTrue(employee.matricule.startswith("EMP-"))
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.CREATE, user=self.rh).exists())

    def test_formulaire_invalide_reste_sur_la_page(self):
        self.client.force_login(self.rh)
        resp = self.client.post(reverse("organization:employee_create"), {"first_name": "X"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Employee.objects.filter(first_name="X").exists())

    def test_modification_historise_le_salaire(self):
        self.client.force_login(self.rh)
        resp = self.client.post(
            reverse("organization:employee_edit", args=[self.emp.pk]),
            {"first_name": "Yasmine", "last_name": "Gharbi", "job_title": "Lead", "hire_date": "2024-01-15",
             "contract_type": "CDI", "base_salary": "2600", "is_active": "on", "department": self.dept.pk,
             "manager": self.manager.pk, "user": self.emp_user.pk},
        )  # fmt: skip
        self.assertEqual(resp.status_code, 302)
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.base_salary, Decimal("2600"))
        self.assertEqual(self.emp.history.count(), 2)
        log = AuditLog.objects.filter(action=AuditLog.Action.UPDATE).first()
        self.assertNotIn("2600", log.description)  # le journal ne contient pas de montant

    def test_desactivation_desactive_aussi_le_compte(self):
        self.client.force_login(self.rh)
        self.client.post(reverse("organization:employee_deactivate", args=[self.emp.pk]))
        self.emp.refresh_from_db()
        self.emp_user.refresh_from_db()
        self.assertFalse(self.emp.is_active)
        self.assertFalse(self.emp_user.is_active)
        self.assertIsNotNone(self.emp.exit_date)

    def test_desactivation_en_get_refusee(self):
        self.client.force_login(self.rh)
        self.assertEqual(self.client.get(reverse("organization:employee_deactivate", args=[self.emp.pk])).status_code, 405)

    # --- recherche, filtres, export --------------------------------------- #
    def test_recherche_filtres_et_tri(self):
        self.client.force_login(self.rh)
        url = reverse("organization:employee_list")
        names = lambda resp: [e.last_name for e in resp.context["page"]]  # noqa: E731
        self.assertEqual(names(self.client.get(url, {"q": "gharbi"})), ["Gharbi"])
        self.assertEqual(names(self.client.get(url, {"sort": "-salary"})), ["Ben Ali", "Gharbi", "Zouari"])
        self.other.deactivate()
        self.assertEqual(len(names(self.client.get(url))), 2)  # actifs par défaut
        self.assertEqual(names(self.client.get(url, {"status": "inactif"})), ["Zouari"])

    def test_export_csv(self):
        self.client.force_login(self.rh)
        resp = self.client.get(reverse("organization:employee_export"))
        self.assertEqual(resp["Content-Type"], "text/csv; charset=utf-8")
        body = resp.content.decode("utf-8-sig")
        self.assertIn("Matricule;Nom;Prénom", body)
        self.assertIn("Gharbi", body)
        self.client.force_login(self.emp_user)
        self.assertEqual(self.client.get(reverse("organization:employee_export")).status_code, 403)

    # --- contrats ----------------------------------------------------------- #
    def test_contrat_actif_met_a_jour_salaire_et_type(self):
        self.client.force_login(self.rh)
        self.client.post(
            reverse("organization:contract_create", args=[self.emp.pk]),
            {"contract_type": "CDD", "start_date": "2025-01-01", "end_date": "2025-12-31", "salary": "2300", "status": "ACTIF"},
        )
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.contract_type, "CDD")
        self.assertEqual(self.emp.base_salary, Decimal("2300"))
        self.assertEqual(self.emp.contracts.count(), 1)

    # --- documents ---------------------------------------------------------- #
    def _upload(self):
        self.client.force_login(self.rh)
        file = SimpleUploadedFile("cin.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        self.client.post(
            reverse("organization:document_upload", args=[self.emp.pk]),
            {"doc_type": "CIN", "title": "CIN Yasmine", "file": file},
        )
        return Document.objects.get(title="CIN Yasmine")

    def test_telechargement_securise_des_documents(self):
        doc = self._upload()
        url = reverse("organization:document_download", args=[doc.pk])
        self.client.force_login(self.rh)
        self.assertEqual(b"".join(self.client.get(url).streaming_content), b"%PDF-1.4 test")
        self.client.force_login(self.emp_user)  # propriétaire
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.other_user)  # un autre employé
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.manager_user)  # même le manager
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_extension_interdite(self):
        self.client.force_login(self.rh)
        file = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream")
        self.client.post(
            reverse("organization:document_upload", args=[self.emp.pk]),
            {"doc_type": "AUTRE", "title": "Danger", "file": file},
        )
        self.assertFalse(Document.objects.filter(title="Danger").exists())

    def test_suppression_efface_le_fichier(self):
        doc = self._upload()
        path = doc.file.path
        self.client.post(reverse("organization:document_delete", args=[doc.pk]))
        self.assertFalse(Document.objects.filter(pk=doc.pk).exists())
        import os

        self.assertFalse(os.path.exists(path))

    # --- profil, départements, organigramme -------------------------------- #
    def test_mon_profil(self):
        self.client.force_login(self.emp_user)
        self.assertRedirects(self.client.get(reverse("organization:my_profile")), reverse("organization:employee_detail", args=[self.emp.pk]))
        self.client.post(reverse("organization:my_profile_edit"), {"phone": "20123456", "address": "Tunis"})
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.phone, "20123456")

    def test_l_employe_ne_peut_pas_modifier_son_salaire_via_son_profil(self):
        self.client.force_login(self.emp_user)
        self.client.post(reverse("organization:my_profile_edit"), {"phone": "1", "address": "x", "base_salary": "99999"})
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.base_salary, Decimal("2100"))

    def test_departements_rh_et_admin(self):
        admin = User.objects.create_user("adm", password="x", role=User.Role.ADMIN)
        url = reverse("organization:department_list")
        self.client.force_login(self.emp_user)
        self.assertEqual(self.client.get(url).status_code, 403)
        for user in (self.rh, admin):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(reverse("organization:department_create"), {"name": "Finance", "description": ""})
        self.assertTrue(Department.objects.filter(name="Finance").exists())

    def test_suppression_d_un_departement_garde_les_employes(self):
        self.client.force_login(self.rh)
        self.client.post(reverse("organization:department_delete", args=[self.dept.pk]))
        self.emp.refresh_from_db()
        self.assertIsNone(self.emp.department)

    def test_api_organigramme(self):
        self.client.force_login(self.emp_user)
        data = json.loads(self.client.get(reverse("organization:org_chart_data")).content)
        roots = {n["name"]: n for n in data["children"]}
        self.assertIn("Karim Ben Ali", roots)
        self.assertEqual([c["name"] for c in roots["Karim Ben Ali"]["children"]], ["Yasmine Gharbi"])
        self.client.logout()
        self.assertEqual(self.client.get(reverse("organization:org_chart_data")).status_code, 302)
