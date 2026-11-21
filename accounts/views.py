from datetime import time, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from attendance.models import Attendance
from audit.models import AuditLog, log_action
from leaves.models import Holiday, LeaveRequest, LeaveType
from organization.models import Department, Employee

from .forms import StyledPasswordChangeForm


@login_required
def home(request):
    """Redirige chaque utilisateur vers le tableau de bord adapté à son rôle."""
    user = request.user
    if user.is_admin_role:
        return redirect("administration:dashboard")

    today = timezone.localdate()
    now_time = timezone.localtime().time()
    work_start = getattr(settings, "WORK_START_TIME", time(9, 0))
    work_end = getattr(settings, "WORK_END_TIME", time(17, 0))
    is_late = now_time > work_start
    is_past_5pm = now_time >= work_end
    clock_in_status = Attendance.Status.LATE if is_late else Attendance.Status.PRESENT
    clock_in_class = "btn-warning text-dark fw-bold" if is_late else "btn-primary text-white fw-bold"
    clock_in_label = "Pointer (En retard)" if is_late else "Pointer (À l'heure)"

    # 1. Espace Ressources Humaines (RH)
    if user.is_rh:
        hr_employee = user.employee_profile
        my_today_attendance = (
            Attendance.objects.filter(employee=hr_employee, date=today).first() if hr_employee else None
        )
        active_employees = Employee.objects.filter(is_active=True)
        active_employees_count = active_employees.count()
        departments_count = Department.objects.count()

        on_leave_today_count = LeaveRequest.objects.filter(
            status=LeaveRequest.Status.APPROVED,
            start_date__lte=today,
            end_date__gte=today,
        ).count()

        pending_leaves_qs = (
            LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING)
            .select_related("employee", "leave_type")
            .order_by("-created_at")
        )
        pending_leaves_count = pending_leaves_qs.count()

        attendances_today = Attendance.objects.filter(date=today)
        present_today_count = attendances_today.filter(status=Attendance.Status.PRESENT).count()
        late_today_count = attendances_today.filter(status=Attendance.Status.LATE).count()
        absent_today_count = attendances_today.filter(status=Attendance.Status.ABSENT).count()

        recent_employees = active_employees.select_related("department").order_by("-hire_date")[:5]

        # Répartition des employés par département
        dept_distribution = Department.objects.annotate(
            emp_count=Count("employees", filter=Q(employees__is_active=True))
        ).order_by("name")
        dept_labels = [d.name for d in dept_distribution]
        dept_data = [d.emp_count for d in dept_distribution]
        no_dept_count = Employee.objects.filter(is_active=True, department__isnull=True).count()
        if no_dept_count > 0:
            dept_labels.append("Sans affectation")
            dept_data.append(no_dept_count)
        dept_stats = list(zip(dept_labels, dept_data))
        max_dept_count = max(dept_data) if dept_data else 1

        context = {
            "employee": hr_employee,
            "my_today_attendance": my_today_attendance,
            "clock_in_status": clock_in_status,
            "clock_in_class": clock_in_class,
            "clock_in_label": clock_in_label,
            "is_late": is_late,
            "is_past_5pm": is_past_5pm,
            "active_employees_count": active_employees_count,
            "departments_count": departments_count,
            "on_leave_today_count": on_leave_today_count,
            "pending_leaves_count": pending_leaves_count,
            "pending_leaves": pending_leaves_qs[:5],
            "present_today_count": present_today_count,
            "late_today_count": late_today_count,
            "absent_today_count": absent_today_count,
            "recent_employees": recent_employees,
            "dept_labels": dept_labels,
            "dept_data": dept_data,
            "dept_stats": dept_stats,
            "max_dept_count": max(max_dept_count, 1),
            "banner_subtitle": "Supervision globale des effectifs, du pointage et des demandes de congés",
        }
        return render(request, "dashboards/dashboard_rh.html", context)

    # 2. Espace Manager
    if user.role == user.Role.MANAGER:
        employee = user.employee_profile
        team_count = 0
        team_present_count = 0
        team_on_leave_count = 0
        team_pending_leaves = []
        team_status_list = []

        headed = employee.headed_departments.first() if employee else None
        department_name = (
            headed.name
            if headed
            else (employee.department.name if employee and employee.department else None)
        )
        role_badge = f"Manager • {department_name}" if department_name else "Manager"
        subtitle = (
            f"Supervision de l'équipe {department_name}, présence quotidienne et suivi des congés"
            if department_name
            else "Supervision de votre équipe, présence quotidienne et suivi des congés"
        )

        if employee is not None:
            team_qs = employee.subordinates.filter(is_active=True).select_related("department")
            team_count = team_qs.count()

            team_attendances = {
                att.employee_id: att
                for att in Attendance.objects.filter(employee__in=team_qs, date=today)
            }

            team_active_leaves = {
                lr.employee_id: lr
                for lr in LeaveRequest.objects.filter(
                    employee__in=team_qs,
                    status=LeaveRequest.Status.APPROVED,
                    start_date__lte=today,
                    end_date__gte=today,
                ).select_related("leave_type")
            }
            team_on_leave_count = len(team_active_leaves)

            for member in team_qs:
                att = team_attendances.get(member.id)
                lv = team_active_leaves.get(member.id)
                if lv:
                    status_label = f"En congé ({lv.leave_type.name})"
                    status_badge = "warning"
                elif att and att.status == Attendance.Status.PRESENT:
                    status_label = f"Présent ({att.check_in_time.strftime('%H:%M') if att.check_in_time else 'Pointé'})"
                    status_badge = "success"
                    team_present_count += 1
                elif att and att.status == Attendance.Status.LATE:
                    status_label = f"En retard ({att.check_in_time.strftime('%H:%M') if att.check_in_time else 'Pointé'})"
                    status_badge = "danger"
                    team_present_count += 1
                elif is_past_5pm:
                    status_label = "Absent"
                    status_badge = "danger"
                else:
                    status_label = "Non pointé"
                    status_badge = "secondary"

                team_status_list.append({
                    "employee": member,
                    "status_label": status_label,
                    "status_badge": status_badge,
                    "attendance": att,
                    "leave": lv,
                })

            team_pending_leaves = (
                LeaveRequest.objects.filter(
                    employee__in=team_qs,
                    status=LeaveRequest.Status.PENDING,
                )
                .select_related("employee", "leave_type")
                .order_by("-created_at")[:5]
            )

        my_today_attendance = (
            Attendance.objects.filter(employee=employee, date=today).first() if employee else None
        )

        team_pending_count = len(team_pending_leaves)

        context = {
            "employee": employee,
            "department_name": department_name,
            "role_badge": role_badge,
            "banner_subtitle": subtitle,
            "clock_in_status": clock_in_status,
            "clock_in_class": clock_in_class,
            "clock_in_label": clock_in_label,
            "is_late": is_late,
            "is_past_5pm": is_past_5pm,
            "team_count": team_count,
            "team_present_count": team_present_count,
            "team_on_leave_count": team_on_leave_count,
            "team_pending_count": team_pending_count,
            "team_status_list": team_status_list,
            "team_pending_leaves": team_pending_leaves,
            "my_today_attendance": my_today_attendance,
        }
        return render(request, "dashboards/dashboard_manager.html", context)

    # 3. Espace Employé (ou autre rôle collaborateur)
    employee = user.employee_profile
    today_attendance = None
    recent_attendances = []
    my_leaves = []
    annual_days_taken = 0
    annual_quota = 30
    pending_leaves_count = 0
    approved_leaves_count = 0

    if employee is not None:
        today_attendance = Attendance.objects.filter(employee=employee, date=today).first()
        recent_attendances = Attendance.objects.filter(employee=employee).order_by("-date")[:5]
        my_leaves = (
            LeaveRequest.objects.filter(employee=employee)
            .select_related("leave_type")
            .order_by("-created_at")[:5]
        )

        year_leaves = (
            LeaveRequest.objects.filter(
                employee=employee,
                status=LeaveRequest.Status.APPROVED,
                start_date__year=today.year,
            ).aggregate(total=Sum("days_count"))["total"]
            or 0
        )
        annual_days_taken = year_leaves

        annual_leave_type = (
            LeaveType.objects.filter(name__icontains="annuel").first()
            or LeaveType.objects.filter(annual_days__gt=0).first()
        )
        if annual_leave_type and annual_leave_type.annual_days > 0:
            annual_quota = annual_leave_type.annual_days

        pending_leaves_count = LeaveRequest.objects.filter(
            employee=employee, status=LeaveRequest.Status.PENDING
        ).count()
        approved_leaves_count = LeaveRequest.objects.filter(
            employee=employee, status=LeaveRequest.Status.APPROVED
        ).count()

    upcoming_holidays = Holiday.objects.filter(date__gte=today).order_by("date")[:4]

    context = {
        "employee": employee,
        "today_attendance": today_attendance,
        "recent_attendances": recent_attendances,
        "my_leaves": my_leaves,
        "annual_days_taken": annual_days_taken,
        "annual_quota": annual_quota,
        "annual_remaining": max(0, annual_quota - annual_days_taken),
        "pending_leaves_count": pending_leaves_count,
        "approved_leaves_count": approved_leaves_count,
        "documents_count": employee.documents.count() if employee is not None else 0,
        "upcoming_holidays": upcoming_holidays,
        "clock_in_status": clock_in_status,
        "clock_in_class": clock_in_class,
        "clock_in_label": clock_in_label,
        "is_late": is_late,
        "is_past_5pm": is_past_5pm,
        "banner_subtitle": "Votre espace collaborateur : fiche personnelle, présences, congés et documents",
    }
    return render(request, "dashboards/dashboard_employee.html", context)


class RateLimitedLoginView(auth_views.LoginView):
    """Connexion avec limitation de débit (cahier des charges, § 10).

    Après LOGIN_MAX_ATTEMPTS échecs pour un même couple (identifiant, adresse IP),
    la connexion est refusée pendant LOGIN_LOCKOUT_SECONDS secondes.
    """

    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def _cache_key(self):
        username = self.request.POST.get("username", "").strip().lower()
        ip = self.request.META.get("REMOTE_ADDR", "")
        return f"login-failures:{username}:{ip}"

    def post(self, request, *args, **kwargs):
        if cache.get(self._cache_key(), 0) >= settings.LOGIN_MAX_ATTEMPTS:
            form = self.get_form()
            form.add_error(None, "Trop de tentatives de connexion. Réessayez dans quelques minutes.")
            response = self.render_to_response(self.get_context_data(form=form))
            response.status_code = 429
            return response
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        key = self._cache_key()
        cache.add(key, 0, settings.LOGIN_LOCKOUT_SECONDS)  # crée le compteur s'il n'existe pas
        try:
            cache.incr(key)
        except ValueError:  # le compteur a expiré entre-temps
            cache.set(key, 1, settings.LOGIN_LOCKOUT_SECONDS)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(self._cache_key())
        return super().form_valid(form)


class PasswordChangeView(auth_views.PasswordChangeView):
    """L'utilisateur modifie son propre mot de passe (EF-AUT-04)."""

    form_class = StyledPasswordChangeForm
    template_name = "registration/password_change_form.html"
    success_url = reverse_lazy("organization:my_profile")

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request.user, AuditLog.Action.UPDATE, self.request.user, "Mot de passe modifié")
        messages.success(self.request, "Votre mot de passe a été modifié.")
        return response