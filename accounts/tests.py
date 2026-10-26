from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from audit.models import AuditLog

from .permissions import role_required

User = get_user_model()


class RoleRequiredTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = role_required("RH")(lambda request: HttpResponse("ok"))

    def _call(self, user):
        request = self.factory.get("/")
        request.user = user
        return self.view(request)

    def test_role_autorise(self):
        user = User.objects.create_user("rh", password="x", role=User.Role.RH)
        self.assertEqual(self._call(user).status_code, 200)

    def test_role_refuse(self):
        user = User.objects.create_user("emp", password="x", role=User.Role.EMPLOYE)
        with self.assertRaises(PermissionDenied):
            self._call(user)

    def test_superuser_passe_toujours(self):
        user = User.objects.create_superuser("root", password="x")
        self.assertEqual(self._call(user).status_code, 200)


class UserModelTests(TestCase):
    def test_role_par_defaut_et_proprietes(self):
        user = User.objects.create_user("u", password="x")
        self.assertEqual(user.role, User.Role.EMPLOYE)
        self.assertFalse(user.is_admin_role)
        self.assertIsNone(user.employee_profile)  # pas de fiche liée : pas d'exception


class LoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("eya", password="Bon-Mot-De-Passe-1", role=User.Role.EMPLOYE)

    def test_connexion_reussie_journalisee(self):
        resp = self.client.post(reverse("login"), {"username": "eya", "password": "Bon-Mot-De-Passe-1"})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.LOGIN, user=self.user).exists())

    def test_echec_journalise(self):
        self.client.post(reverse("login"), {"username": "eya", "password": "faux"})
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.LOGIN, user=None, description__contains="eya").exists())

    @override_settings(LOGIN_MAX_ATTEMPTS=3)
    def test_blocage_apres_trop_d_echecs(self):
        for _ in range(3):
            self.client.post(reverse("login"), {"username": "eya", "password": "faux"})
        # Même avec le bon mot de passe, la connexion est refusée pendant le blocage.
        resp = self.client.post(reverse("login"), {"username": "eya", "password": "Bon-Mot-De-Passe-1"})
        self.assertEqual(resp.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_succes_remet_le_compteur_a_zero(self):
        self.client.post(reverse("login"), {"username": "eya", "password": "faux"})
        self.client.post(reverse("login"), {"username": "eya", "password": "Bon-Mot-De-Passe-1"})
        self.client.logout()
        self.assertEqual(cache.get("login-failures:eya:127.0.0.1"), None)


class PasswordChangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("eya", password="Ancien-Mot-De-Passe-1")

    def test_page_reservee_aux_connectes(self):
        self.assertEqual(self.client.get(reverse("password_change")).status_code, 302)

    def test_changement_du_mot_de_passe(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("password_change")).status_code, 200)
        resp = self.client.post(
            reverse("password_change"),
            {"old_password": "Ancien-Mot-De-Passe-1", "new_password1": "Nouveau-Mot-De-Passe-2", "new_password2": "Nouveau-Mot-De-Passe-2"},
        )
        self.assertRedirects(resp, reverse("home"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Nouveau-Mot-De-Passe-2"))
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.UPDATE, user=self.user).exists())

    def test_ancien_mot_de_passe_faux(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("password_change"),
            {"old_password": "faux", "new_password1": "Nouveau-Mot-De-Passe-2", "new_password2": "Nouveau-Mot-De-Passe-2"},
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Ancien-Mot-De-Passe-1"))


class HomeRedirectTests(TestCase):
    def test_redirection_selon_le_role(self):
        admin = User.objects.create_user("a", password="x", role=User.Role.ADMIN)
        rh = User.objects.create_user("r", password="x", role=User.Role.RH)
        emp = User.objects.create_user("e", password="x", role=User.Role.EMPLOYE)
        self.client.force_login(admin)
        self.assertRedirects(self.client.get(reverse("home")), reverse("administration:dashboard"), fetch_redirect_response=False)
        self.client.force_login(rh)
        self.assertRedirects(self.client.get(reverse("home")), reverse("organization:employee_list"), fetch_redirect_response=False)
        self.client.force_login(emp)
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
