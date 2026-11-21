from datetime import datetime

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import rh_or_admin
from audit.models import AuditLog, log_action
from organization.models import Employee

from .models import LeaveRequest, LeaveType


@rh_or_admin
def leave_list(request):
    """Liste globale des congés avec statut et filtres."""
    status_filter = request.GET.get("status", "")
    type_filter = request.GET.get("type", "")
    q = request.GET.get("q", "").strip()

    leaves = (
        LeaveRequest.objects.select_related("employee", "leave_type")
        .order_by("-start_date")
    )

    if status_filter:
        leaves = leaves.filter(status=status_filter)
    if type_filter:
        leaves = leaves.filter(leave_type_id=type_filter)
    if q:
        leaves = leaves.filter(
            Q(employee__first_name__icontains=q)
            | Q(employee__last_name__icontains=q)
            | Q(employee__matricule__icontains=q)
            | Q(reason__icontains=q)
        )

    counts = {
        "total": LeaveRequest.objects.count(),
        "pending": LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING).count(),
        "approved": LeaveRequest.objects.filter(status=LeaveRequest.Status.APPROVED).count(),
        "rejected": LeaveRequest.objects.filter(status=LeaveRequest.Status.REJECTED).count(),
    }

    page = Paginator(leaves, 15).get_page(request.GET.get("page"))
    return render(
        request,
        "leaves/leave_list.html",
        {
            "page": page,
            "counts": counts,
            "leave_types": LeaveType.objects.all(),
            "statuses": LeaveRequest.Status.choices,
            "selected_status": status_filter,
            "selected_type": type_filter,
            "q": q,
            "employees": Employee.objects.filter(is_active=True).order_by("last_name"),
        },
    )


@rh_or_admin
@require_POST
def leave_approve(request, pk):
    """Approuve une demande de congé."""
    leave = get_object_or_404(LeaveRequest, pk=pk)
    leave.status = LeaveRequest.Status.APPROVED
    leave.save(update_fields=["status"])
    log_action(
        request.user,
        AuditLog.Action.UPDATE,
        leave,
        f"Congé approuvé pour {leave.employee.full_name} ({leave.start_date:%d/%m/%Y} au {leave.end_date:%d/%m/%Y})",
    )
    messages.success(request, f"Le congé de {leave.employee.full_name} a été approuvé.")
    return redirect("leaves:leave_list")


@rh_or_admin
@require_POST
def leave_reject(request, pk):
    """Refuse une demande de congé."""
    leave = get_object_or_404(LeaveRequest, pk=pk)
    leave.status = LeaveRequest.Status.REJECTED
    leave.save(update_fields=["status"])
    log_action(
        request.user,
        AuditLog.Action.UPDATE,
        leave,
        f"Congé refusé pour {leave.employee.full_name} ({leave.start_date:%d/%m/%Y} au {leave.end_date:%d/%m/%Y})",
    )
    messages.warning(request, f"Le congé de {leave.employee.full_name} a été refusé.")
    return redirect("leaves:leave_list")


@rh_or_admin
@require_POST
def leave_create(request):
    """Enregistre un congé pour un employé."""
    emp_id = request.POST.get("employee_id")
    type_id = request.POST.get("leave_type_id")
    start_date_str = request.POST.get("start_date")
    end_date_str = request.POST.get("end_date")
    reason = request.POST.get("reason", "").strip()

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        messages.error(request, "Dates de congé invalides.")
        return redirect("leaves:leave_list")

    if end_date < start_date:
        messages.error(request, "La date de fin ne peut pas précéder la date de début.")
        return redirect("leaves:leave_list")

    employee = get_object_or_404(Employee, pk=emp_id)
    leave_type = get_object_or_404(LeaveType, pk=type_id)
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
        request.user,
        AuditLog.Action.CREATE,
        leave,
        f"Congé accordé à {employee.full_name} : {leave_type.name} du {start_date:%d/%m} au {end_date:%d/%m} ({days_count} j)",
    )
    messages.success(request, f"Congé créé avec succès pour {employee.full_name} ({days_count} j).")
    return redirect("leaves:leave_list")
