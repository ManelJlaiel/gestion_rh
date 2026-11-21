from datetime import date, time
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from attendance.models import Attendance
from organization.models import Department, Employee


class AttendanceFeatureTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Informatique")
        self.admin_user = User.objects.create_user(
            username="admin_test", password="Password123!", role="ADMIN", is_staff=True, is_superuser=True
        )
        self.rh_user = User.objects.create_user(
            username="rh_test", password="Password123!", role="RH"
        )
        self.emp_user = User.objects.create_user(
            username="emp_test", password="Password123!", role="EMPLOYE"
        )
        self.employee = Employee.objects.create(
            user=self.emp_user,
            matricule="EMP-TEST",
            first_name="Amine",
            last_name="Test",
            department=self.dept,
            hire_date=date(2024, 1, 1),
            base_salary=2000.00,
            is_active=True,
        )

    def test_employee_can_check_in(self):
        self.client.force_login(self.emp_user)
        response = self.client.post(
            reverse("attendance:mark"),
            {"next": reverse("home")},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        att = Attendance.objects.get(employee=self.employee, date=timezone.localdate())
        self.assertIsNotNone(att.check_in_time)
        self.assertIn(att.status, [Attendance.Status.PRESENT, Attendance.Status.LATE])

    def test_employee_can_check_out(self):
        today = timezone.localdate()
        att = Attendance.objects.create(
            employee=self.employee,
            date=today,
            status=Attendance.Status.PRESENT,
            check_in_time=time(8, 55),
        )
        self.client.force_login(self.emp_user)
        response = self.client.post(
            reverse("attendance:mark"),
            {"action": "check_out", "next": reverse("home")},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        att.refresh_from_db()
        self.assertIsNotNone(att.check_out_time)

    def test_admin_and_rh_see_arrival_and_departure_in_dashboard(self):
        today = timezone.localdate()
        Attendance.objects.create(
            employee=self.employee,
            date=today,
            status=Attendance.Status.PRESENT,
            check_in_time=time(8, 45),
            check_out_time=time(17, 30),
        )
        # Check as Admin
        self.client.force_login(self.admin_user)
        resp_admin = self.client.get(reverse("attendance:dashboard"))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertContains(resp_admin, "08:45")
        self.assertContains(resp_admin, "17:30")

        # Check as RH
        self.client.force_login(self.rh_user)
        resp_rh = self.client.get(reverse("attendance:dashboard"))
        self.assertEqual(resp_rh.status_code, 200)
        self.assertContains(resp_rh, "08:45")
        self.assertContains(resp_rh, "17:30")

    def test_admin_can_mark_employee_check_out(self):
        today = timezone.localdate()
        att = Attendance.objects.create(
            employee=self.employee,
            date=today,
            status=Attendance.Status.PRESENT,
            check_in_time=time(9, 0),
        )
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("attendance:mark"),
            {"action": "check_out", "employee_id": self.employee.id, "date": str(today)},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        att.refresh_from_db()
        self.assertIsNotNone(att.check_out_time)
