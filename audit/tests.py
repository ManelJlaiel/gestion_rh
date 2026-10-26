from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from organization.models import Department

from .models import AuditLog, log_action, log_read

User = get_user_model()


class LogActionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("eya", password="x")
        self.dept = Department.objects.create(name="Production")

    def test_enregistre_utilisateur_objet_et_action(self):
        log = log_action(self.user, AuditLog.Action.CREATE, self.dept, "Département créé")
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.action, "CREATE")
        self.assertEqual(log.object_type, "département")
        self.assertEqual(log.object_id, str(self.dept.pk))

    def test_utilisateur_anonyme_ou_absent(self):
        self.assertIsNone(log_action(AnonymousUser(), AuditLog.Action.LOGIN).user)
        self.assertIsNone(log_action(None, AuditLog.Action.LOGIN).user)

    def test_description_tronquee_a_255_caracteres(self):
        log = log_action(self.user, AuditLog.Action.UPDATE, self.dept, "x" * 400)
        self.assertEqual(len(log.description), 255)

    def test_log_read(self):
        log = log_read(self.user, self.dept)
        self.assertEqual(log.action, AuditLog.Action.READ)

    def test_les_plus_recents_d_abord(self):
        first = log_action(self.user, AuditLog.Action.READ)
        second = log_action(self.user, AuditLog.Action.READ)
        self.assertEqual(list(AuditLog.objects.all()), [second, first])

    def test_le_journal_survit_a_la_suppression_de_l_utilisateur(self):
        log = log_action(self.user, AuditLog.Action.READ)
        self.user.delete()
        log.refresh_from_db()
        self.assertIsNone(log.user)
