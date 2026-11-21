from decimal import Decimal

from django.db.models import Avg, Sum
from django.shortcuts import render

from accounts.permissions import rh_or_admin
from organization.models import Employee

from .models import PayrollRate


@rh_or_admin
def payroll_dashboard(request):
    """Tableau de bord de la paie et masse salariale."""
    employees = (
        Employee.objects.filter(is_active=True)
        .select_related("department")
        .order_by("last_name", "first_name")
    )

    stats = employees.aggregate(
        total_payroll=Sum("base_salary"),
        avg_salary=Avg("base_salary"),
    )
    total_payroll = stats["total_payroll"] or Decimal("0.000")
    avg_salary = stats["avg_salary"] or Decimal("0.000")

    # Taux CNSS en vigueur
    cnss_rate_obj = PayrollRate.objects.filter(code=PayrollRate.Code.CNSS).first()
    cnss_pct = cnss_rate_obj.rate if cnss_rate_obj else Decimal("9.18")

    # Grille de taux enregistrée
    rates = PayrollRate.objects.all().order_by("code", "lower_bound")

    rows = []
    for emp in employees:
        base = emp.base_salary or Decimal("0.000")
        cnss_deduction = (base * (cnss_pct / Decimal("100"))).quantize(Decimal("0.001"))
        taxable_salary = base - cnss_deduction
        rows.append({
            "employee": emp,
            "base_salary": base,
            "cnss_deduction": cnss_deduction,
            "taxable_salary": taxable_salary,
        })

    return render(
        request,
        "payroll/dashboard.html",
        {
            "rows": rows,
            "total_payroll": total_payroll,
            "avg_salary": avg_salary,
            "total_employees": employees.count(),
            "cnss_pct": cnss_pct,
            "rates": rates,
        },
    )
