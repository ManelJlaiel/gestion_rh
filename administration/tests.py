from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from audit.models import AuditLog
from leaves.models import LeaveType

User = get_user_model()


class AdministrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="x-Pass-123", role=User.Role.ADMIN)
        self.rh = User.objects.create_user("rh", password="x-Pass-123", role=User.Role.RH)
        self.emp = User.objects.create_user("emp", password="x-Pass-123", role=User.Role.EMPLOYE)

    def test_pages_reservees_a_l_admin(self):
        url = reverse("administration:dashboard")
        self.assertEqual(self.client.get(url).status_code, 302)  # non connecté → connexion
        self.client.force_login(self.rh)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_toutes_les_pages_s_affichent(self):
        self.client.force_login(self.admin)
        names = ["dashboard", "settings_home", "users", "user_add", "audit"]
        for name in names:
            self.assertEqual(self.client.get(reverse(f"administration:{name}")).status_code, 200, name)
        for section in ["types-conges", "jours-feries", "departements", "taux-paie"]:
            self.assertEqual(self.client.get(reverse("administration:settings", args=[section])).status_code, 200)
            self.assertEqual(self.client.get(reverse("administration:settings_add", args=[section])).status_code, 200)

    def test_ajout_type_conge_journalise(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse("administration:settings_add", args=["types-conges"]),
            {"name": "Congé annuel", "annual_days": 30},
        )
        self.assertRedirects(resp, reverse("administration:settings", args=["types-conges"]))
        self.assertTrue(LeaveType.objects.filter(name="Congé annuel").exists())
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.CREATE, user=self.admin).exists())

    def test_creation_compte(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse("administration:user_add"),
            {"username": "nouveau", "first_name": "A", "last_name": "B", "email": "a@b.tn", "role": "MANAGER", "password": "Un-Mot-De-Passe-2026"},
        )
        self.assertRedirects(resp, reverse("administration:users"))
        user = User.objects.get(username="nouveau")
        self.assertEqual(user.role, User.Role.MANAGER)
        self.assertTrue(user.check_password("Un-Mot-De-Passe-2026"))

    def test_desactivation_et_protection_de_soi(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("administration:user_toggle", args=[self.emp.pk]))
        self.emp.refresh_from_db()
        self.assertFalse(self.emp.is_active)
        self.client.post(reverse("administration:user_toggle", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_toggle_htmx_renvoie_la_ligne(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("administration:user_toggle", args=[self.emp.pk]), HTTP_HX_REQUEST="true")
        self.assertContains(resp, f'id="user-{self.emp.pk}"')

    def test_reinitialisation_mot_de_passe(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse("administration:user_reset", args=[self.emp.pk]))
        temp = resp.context["temp_password"]
        self.emp.refresh_from_db()
        self.assertTrue(self.emp.check_password(temp))

    def test_admin_ne_peut_pas_retirer_son_propre_role(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("administration:user_edit", args=[self.admin.pk]), {"role": "EMPLOYE"})
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.ADMIN)

    def test_filtre_audit(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("administration:audit"), {"action": "LOGIN"})
        self.assertEqual(resp.status_code, 200)
