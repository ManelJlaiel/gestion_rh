from datetime import date, datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from audit.models import AuditLog, log_action
from leaves.models import LeaveRequest, LeaveType
from organization.models import Department, Employee

from .models import Attendance



@login_required
def attendance_dashboard(request):
    """Tableau de bord : Pointage des présences & Suivi des congés."""
    user = request.user
    if not (user.is_admin_role or user.role == "RH" or user.role == "MANAGER"):
        return redirect("home")

    date_str = request.GET.get("date", "")
    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else timezone.localdate()
    except ValueError:
        selected_date = timezone.localdate()

    dept_id = request.GET.get("department", "")
    role_filter = request.GET.get("role", "")
    q = request.GET.get("q", "").strip()

    # Seuls les employés et managers sont soumis au pointage (pas le RH ni l'Admin)
    employees = (
        Employee.objects.filter(is_active=True)
        .exclude(user__role__in=["RH", "ADMIN"])
        .select_related("department", "user")
        .order_by("last_name", "first_name")
    )
    if dept_id:
        employees = employees.filter(department_id=dept_id)
    if role_filter:
        employees = employees.filter(user__role=role_filter)
    if q:
        employees = employees.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(matricule__icontains=q)
        )

    attendances_map = {
        att.employee_id: att
        for att in Attendance.objects.filter(date=selected_date)
    }

    active_leaves_map = {
        lr.employee_id: lr
        for lr in LeaveRequest.objects.filter(
            status=LeaveRequest.Status.APPROVED,
            start_date__lte=selected_date,
            end_date__gte=selected_date,
        ).select_related("leave_type")
    }

    # Cumul annuel des congés par employé (toute l'année en cours)
    leaves_this_year = LeaveRequest.objects.filter(
        status=LeaveRequest.Status.APPROVED,
        start_date__year=selected_date.year,
    ).values("employee_id").annotate(total=Sum("days_count"))

    yearly_taken_map = {item["employee_id"]: item["total"] for item in leaves_this_year}

    # Quota annuel par défaut défini par l'admin (Paramètres -> Types de congés, ex: 30 j pour Congé annuel)
    annual_leave_type = (
        LeaveType.objects.filter(name__icontains="annuel").first()
        or LeaveType.objects.filter(annual_days__gt=0).first()
    )
    default_annual = annual_leave_type.annual_days if annual_leave_type else 30

    rows = []
    present_count = 0
    late_count = 0
    absent_count = 0
    on_leave_count = 0

    for emp in employees:
        att = attendances_map.get(emp.id)
        current_leave = active_leaves_map.get(emp.id)

        # Total des jours pris cette année
        days_taken = yearly_taken_map.get(emp.id, 0)

        # Quota annuel fixé par l'admin (selon le type de congé ou le quota standard 30 j/an)
        if current_leave and current_leave.leave_type and current_leave.leave_type.annual_days > 0:
            annual_limit = current_leave.leave_type.annual_days
        else:
            annual_limit = default_annual

        remaining_days = max(0, annual_limit - days_taken)
        is_limit_reached = (days_taken >= annual_limit) if annual_limit > 0 else False

        if current_leave:
            on_leave_count += 1
        if att:
            if att.status == Attendance.Status.PRESENT:
                present_count += 1
            elif att.status == Attendance.Status.LATE:
                late_count += 1
            elif att.status == Attendance.Status.ABSENT:
                absent_count += 1

        rows.append({
            "employee": emp,
            "attendance": att,
            "on_leave": bool(current_leave),
            "leave": current_leave,
            "days_taken": days_taken,
            "annual_limit": annual_limit,
            "remaining_days": remaining_days,
            "is_limit_reached": is_limit_reached,
            "role_display": emp.user.get_role_display() if emp.user else "—",
            "role": emp.user.role if emp.user else "",
        })

    my_employee = user.employee_profile
    my_today_attendance = Attendance.objects.filter(employee=my_employee, date=timezone.localdate()).first() if my_employee else None

    from accounts.models import User as UserModel
    departments = Department.objects.all().order_by("name")
    leave_types = LeaveType.objects.all().order_by("name")
    roles = UserModel.Role.choices  # [('EMPLOYE', 'Employé'), ('MANAGER', 'Manager'), …]

    context = {
        "selected_date": selected_date,
        "is_today": selected_date == timezone.localdate(),
        "rows": rows,
        "departments": departments,
        "leave_types": leave_types,
        "roles": roles,
        "selected_dept": dept_id,
        "selected_role": role_filter,
        "q": q,
        "total_employees": employees.count(),
        "present_count": present_count,
        "late_count": late_count,
        "absent_count": absent_count,
        "on_leave_count": on_leave_count,
        "my_today_attendance": my_today_attendance,
        "my_employee": my_employee,
    }
    return render(request, "attendance/dashboard.html", context)


@login_required
@require_POST
def mark_attendance(request):
    """Enregistre ou met à jour le pointage (Présent / En retard / Absent)."""
    user = request.user
    emp_id = request.POST.get("employee_id")
    status = request.POST.get("status")
    date_str = request.POST.get("date", "")

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else timezone.localdate()
    except ValueError:
        target_date = timezone.localdate()

    if not emp_id and user.employee_profile:
        employee = user.employee_profile
    else:
        if not (user.is_admin_role or user.role == "RH" or user.role == "MANAGER"):
            messages.error(request, "Vous n'avez pas l'autorisation de modifier ce pointage.")
            return redirect("attendance:dashboard")
        employee = get_object_or_404(Employee, pk=emp_id)

    if status not in Attendance.Status.values:
        messages.error(request, "Statut de pointage invalide.")
        return redirect(f"/pointage/?date={target_date}")

    now_time = timezone.localtime().time()
    attendance, created = Attendance.objects.update_or_create(
        employee=employee,
        date=target_date,
        defaults={
            "status": status,
            "check_in_time": now_time if status in (Attendance.Status.PRESENT, Attendance.Status.LATE) else None,
        },
    )

    log_action(
        user,
        AuditLog.Action.UPDATE if not created else AuditLog.Action.CREATE,
        attendance,
        f"Pointage de {employee.full_name} le {target_date:%d/%m/%Y} : {attendance.get_status_display()}",
    )
    messages.success(request, f"Pointage de {employee.full_name} enregistré : {attendance.get_status_display()}.")
    return redirect(f"/pointage/?date={target_date}")


@login_required
@require_POST
def add_leave(request):
    """Enregistre un congé pour un employé."""
    user = request.user
    if not (user.is_admin_role or user.role == "RH"):
        messages.error(request, "Seul le service RH ou un administrateur peut enregistrer un congé.")
        return redirect("attendance:dashboard")

    emp_id = request.POST.get("employee_id")
    leave_type_id = request.POST.get("leave_type_id")
    start_date_str = request.POST.get("start_date")
    end_date_str = request.POST.get("end_date")
    reason = request.POST.get("reason", "").strip()

    employee = get_object_or_404(Employee, pk=emp_id)
    leave_type = get_object_or_404(LeaveType, pk=leave_type_id)

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        messages.error(request, "Dates de congé invalides.")
        return redirect("attendance:dashboard")

    if end_date < start_date:
        messages.error(request, "La date de fin ne peut pas précéder la date de début.")
        return redirect("attendance:dashboard")

    days_count = (end_date - start_date).days + 1

    leave = LeaveRequest.objects.create(
        employee=employee,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        days_count=days_count,
        status=LeaveRequest.Status.APPROVED,
        reason=reason,
    )

    log_action(
        user,
        AuditLog.Action.CREATE,
        leave,
        f"Congé accordé à {employee.full_name} : {leave_type.name} du {start_date:%d/%m} au {end_date:%d/%m} ({days_count} j)",
    )
    messages.success(request, f"Congé enregistré pour {employee.full_name} ({days_count} jour{'s' if days_count > 1 else ''}).")
    return redirect(f"/pointage/?date={start_date}")
