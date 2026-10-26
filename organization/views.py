import csv
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from accounts.permissions import is_rh, rh_only, rh_or_admin
from audit.models import AuditLog, changed_fields, log_action, log_read

from .forms import (
    ContractForm,
    DepartmentForm,
    DocumentForm,
    EmployeeForm,
    EmployeeSelfForm,
)
from .models import Contract, ContractType, Department, Document, Employee
from .permissions import can_view_documents, can_view_employee

SORT_FIELDS = {
    "name": "last_name",
    "matricule": "matricule",
    "department": "department__name",
    "hire_date": "hire_date",
    "salary": "base_salary",
}


# --------------------------------------------------------------------------- #
# Employés
# --------------------------------------------------------------------------- #
def _filtered_employees(request):
    """Recherche, filtres multicritères et tri (EF-EMP-04), partagés par la liste et l'export."""
    employees = Employee.objects.select_related("department", "manager")
    q = request.GET.get("q", "").strip()
    department = request.GET.get("department", "")
    contract_type = request.GET.get("contract_type", "")
    status = request.GET.get("status", "actif")  # par défaut : employés actifs
    sort = request.GET.get("sort", "name")

    if q:
        employees = employees.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(matricule__icontains=q)
            | Q(email__icontains=q)
            | Q(job_title__icontains=q)
        )
    if department.isdigit():
        employees = employees.filter(department_id=department)
    if contract_type in ContractType.values:
        employees = employees.filter(contract_type=contract_type)
    if status == "actif":
        employees = employees.filter(is_active=True)
    elif status == "inactif":
        employees = employees.filter(is_active=False)

    field = SORT_FIELDS.get(sort.lstrip("-"), "last_name")
    employees = employees.order_by(f"-{field}" if sort.startswith("-") else field, "pk")
    filters = {"q": q, "department": department, "contract_type": contract_type, "status": status, "sort": sort}
    return employees, filters


@rh_only
def employee_list(request):
    employees, filters = _filtered_employees(request)
    page = Paginator(employees, 15).get_page(request.GET.get("page"))
    return render(
        request,
        "organization/employee_list.html",
        {
            "page": page,
            "f": filters,
            "departments": Department.objects.all(),
            "contract_types": ContractType.choices,
            "sorts": [
                ("name", "Nom (A → Z)"),
                ("-name", "Nom (Z → A)"),
                ("matricule", "Matricule"),
                ("department", "Département"),
                ("-hire_date", "Embauche récente"),
                ("hire_date", "Embauche ancienne"),
                ("-salary", "Salaire décroissant"),
            ],
        },
    )


@login_required
def employee_detail(request, pk):
    employee = get_object_or_404(Employee.objects.select_related("department", "manager", "user"), pk=pk)
    if not can_view_employee(request.user, employee):
        raise PermissionDenied
    log_read(request.user, employee, f"Consultation de la fiche : {employee}")
    rh = is_rh(request.user)
    context = {
        "employee": employee,
        "is_rh": rh,  # salaire, contrats et historique : RH uniquement
        "contracts": employee.contracts.all() if rh else [],
        "history": employee.history.select_related("history_user")[:10] if rh else [],
        "documents": employee.documents.all() if can_view_documents(request.user, employee) else None,
        "is_self": request.user.employee_profile == employee,
    }
    return render(request, "organization/employee_detail.html", context)


def _sync_account(employee, acting_user):
    """Le compte de connexion suit l'état de l'employé (un ancien employé ne se connecte plus)."""
    account = employee.user
    if account and account != acting_user and account.is_active != employee.is_active:
        account.is_active = employee.is_active
        account.save(update_fields=["is_active"])


@rh_only
def employee_create(request):
    if request.method == "POST":
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save()
            log_action(request.user, AuditLog.Action.CREATE, employee, f"Employé créé : {employee}")
            messages.success(request, f"La fiche de « {employee.full_name} » a été créée.")
            return redirect("organization:employee_detail", pk=employee.pk)
    else:
        form = EmployeeForm()
    return render(request, "organization/form.html", {"form": form, "title": "Nouvel employé", "cancel_url": "organization:employee_list"})


@rh_only
def employee_edit(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == "POST":
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            employee = form.save()
            if "is_active" in form.changed_data:
                _sync_account(employee, request.user)
            log_action(
                request.user, AuditLog.Action.UPDATE, employee,
                f"Employé modifié : {employee} — champs : {changed_fields(form) or 'aucun'}",
            )  # fmt: skip
            messages.success(request, "La fiche a été mise à jour.")
            return redirect("organization:employee_detail", pk=employee.pk)
    else:
        form = EmployeeForm(instance=employee)
    return render(
        request,
        "organization/form.html",
        {"form": form, "title": f"Modifier {employee.full_name}", "cancel_url": "organization:employee_detail", "cancel_arg": employee.pk},
    )


@rh_only
@require_POST
def employee_deactivate(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if employee.user_id == request.user.pk:
        messages.error(request, "Vous ne pouvez pas désactiver votre propre fiche.")
    else:
        employee.deactivate()
        _sync_account(employee, request.user)
        log_action(request.user, AuditLog.Action.UPDATE, employee, f"Employé désactivé : {employee}")
        messages.success(request, f"« {employee.full_name} » a été désactivé (date de sortie conservée).")
    return redirect("organization:employee_detail", pk=employee.pk)


@rh_only
@require_GET
def employee_export_csv(request):
    """Export CSV (ouvrable dans Excel) de la liste filtrée (EF-EMP-05)."""
    employees, _ = _filtered_employees(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="employes.csv"'
    response.write("﻿")  # BOM : Excel reconnaît l'UTF-8 (accents)
    writer = csv.writer(response, delimiter=";")
    writer.writerow(["Matricule", "Nom", "Prénom", "E-mail", "Téléphone", "Poste", "Département", "Manager",
                     "Date d'embauche", "Contrat", "Salaire de base", "Actif", "Date de sortie"])  # fmt: skip
    count = 0
    for e in employees:
        writer.writerow([
            e.matricule, e.last_name, e.first_name, e.email, e.phone, e.job_title,
            e.department or "", e.manager.full_name if e.manager else "",
            e.hire_date, e.get_contract_type_display(), e.base_salary,
            "Oui" if e.is_active else "Non", e.exit_date or "",
        ])  # fmt: skip
        count += 1
    log_action(request.user, AuditLog.Action.READ, None, f"Export CSV des employés ({count} lignes)")
    return response


# --------------------------------------------------------------------------- #
# Profil de l'employé connecté
# --------------------------------------------------------------------------- #
@login_required
def my_profile(request):
    employee = request.user.employee_profile
    if employee is None:
        messages.info(request, "Aucune fiche employé n'est liée à votre compte.")
        return redirect("home")
    return redirect("organization:employee_detail", pk=employee.pk)


@login_required
def my_profile_edit(request):
    employee = request.user.employee_profile
    if employee is None:
        raise PermissionDenied
    if request.method == "POST":
        form = EmployeeSelfForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            log_action(request.user, AuditLog.Action.UPDATE, employee, f"Profil mis à jour par l'employé : {changed_fields(form) or 'aucun'}")
            messages.success(request, "Vos informations ont été mises à jour.")
            return redirect("organization:my_profile")
    else:
        form = EmployeeSelfForm(instance=employee)
    return render(request, "organization/form.html", {"form": form, "title": "Mettre à jour mes informations", "cancel_url": "organization:my_profile"})


# --------------------------------------------------------------------------- #
# Départements
# --------------------------------------------------------------------------- #
@rh_or_admin
def department_list(request):
    departments = Department.objects.select_related("head").annotate(
        headcount=Count("employees", filter=Q(employees__is_active=True))
    )
    return render(request, "organization/department_list.html", {"departments": departments})


@rh_or_admin
def department_create(request):
    if request.method == "POST":
        form = DepartmentForm(request.POST)
        if form.is_valid():
            department = form.save()
            log_action(request.user, AuditLog.Action.CREATE, department, f"Département créé : {department}")
            messages.success(request, f"Le département « {department} » a été créé.")
            return redirect("organization:department_list")
    else:
        form = DepartmentForm()
    return render(request, "organization/form.html", {"form": form, "title": "Nouveau département", "cancel_url": "organization:department_list"})


@rh_or_admin
def department_edit(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == "POST":
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            department = form.save()
            log_action(request.user, AuditLog.Action.UPDATE, department, f"Département modifié : {department}")
            messages.success(request, f"Le département « {department} » a été mis à jour.")
            return redirect("organization:department_list")
    else:
        form = DepartmentForm(instance=department)
    return render(request, "organization/form.html", {"form": form, "title": f"Modifier {department}", "cancel_url": "organization:department_list"})


@rh_or_admin
@require_POST
def department_delete(request, pk):
    department = get_object_or_404(Department, pk=pk)
    name = str(department)
    log_action(request.user, AuditLog.Action.DELETE, department, f"Département supprimé : {name}")
    department.delete()  # les employés restent, sans département (SET_NULL)
    messages.success(request, f"Le département « {name} » a été supprimé.")
    return redirect("organization:department_list")


# --------------------------------------------------------------------------- #
# Contrats
# --------------------------------------------------------------------------- #
def _apply_active_contract(contract):
    """Un contrat en cours met à jour le type de contrat et le salaire de base de l'employé."""
    if contract.status == Contract.Status.ACTIVE:
        employee = contract.employee
        employee.contract_type = contract.contract_type
        employee.base_salary = contract.salary
        employee.save()  # simple_history garde la trace de l'ancien salaire


@rh_only
def contract_create(request, employee_pk):
    employee = get_object_or_404(Employee, pk=employee_pk)
    if request.method == "POST":
        form = ContractForm(request.POST, instance=Contract(employee=employee))
        if form.is_valid():
            contract = form.save()
            _apply_active_contract(contract)
            log_action(request.user, AuditLog.Action.CREATE, contract, f"Contrat créé pour {employee}")
            messages.success(request, "Le contrat a été ajouté.")
            return redirect("organization:employee_detail", pk=employee.pk)
    else:
        form = ContractForm(instance=Contract(employee=employee))
    return render(request, "organization/form.html", {"form": form, "title": f"Nouveau contrat — {employee.full_name}", "cancel_url": "organization:employee_detail", "cancel_arg": employee.pk})


@rh_only
def contract_edit(request, pk):
    contract = get_object_or_404(Contract.objects.select_related("employee"), pk=pk)
    if request.method == "POST":
        form = ContractForm(request.POST, instance=contract)
        if form.is_valid():
            contract = form.save()
            _apply_active_contract(contract)
            log_action(request.user, AuditLog.Action.UPDATE, contract, f"Contrat modifié pour {contract.employee} — champs : {changed_fields(form) or 'aucun'}")
            messages.success(request, "Le contrat a été mis à jour.")
            return redirect("organization:employee_detail", pk=contract.employee_id)
    else:
        form = ContractForm(instance=contract)
    return render(request, "organization/form.html", {"form": form, "title": f"Modifier le contrat — {contract.employee.full_name}", "cancel_url": "organization:employee_detail", "cancel_arg": contract.employee_id})


# --------------------------------------------------------------------------- #
# Documents (téléchargement sécurisé : droits vérifiés à chaque requête)
# --------------------------------------------------------------------------- #
@rh_only
def document_upload(request, employee_pk):
    employee = get_object_or_404(Employee, pk=employee_pk)
    if request.method == "POST":
        form = DocumentForm(request.POST, request.FILES, instance=Document(employee=employee, uploaded_by=request.user))
        if form.is_valid():
            document = form.save()
            log_action(request.user, AuditLog.Action.CREATE, document, f"Document ajouté : {document.title} ({employee})")
            messages.success(request, "Le document a été ajouté.")
            return redirect("organization:employee_detail", pk=employee.pk)
    else:
        form = DocumentForm(instance=Document(employee=employee, uploaded_by=request.user))
    return render(request, "organization/form.html", {"form": form, "multipart": True, "title": f"Ajouter un document — {employee.full_name}", "cancel_url": "organization:employee_detail", "cancel_arg": employee.pk})


@login_required
def document_download(request, pk):
    document = get_object_or_404(Document.objects.select_related("employee"), pk=pk)
    if not can_view_documents(request.user, document.employee):
        raise PermissionDenied
    log_read(request.user, document, f"Téléchargement : {document.title} ({document.employee})")
    return FileResponse(document.file.open("rb"), as_attachment=True, filename=document.filename)


@rh_only
@require_POST
def document_delete(request, pk):
    document = get_object_or_404(Document.objects.select_related("employee"), pk=pk)
    employee_id = document.employee_id
    log_action(request.user, AuditLog.Action.DELETE, document, f"Document supprimé : {document.title} ({document.employee})")
    document.delete()
    messages.success(request, "Le document a été supprimé.")
    return redirect("organization:employee_detail", pk=employee_id)


# --------------------------------------------------------------------------- #
# Organigramme (EF-ORG-01/02) : API JSON consommée plus tard par D3.js / OrgChart.js
# --------------------------------------------------------------------------- #
@login_required
@require_GET
def org_chart_data(request):
    employees = list(Employee.objects.filter(is_active=True).select_related("department"))
    ids = {e.pk for e in employees}
    children = defaultdict(list)
    for e in employees:
        children[e.manager_id].append(e)

    def node(e, seen):
        return {
            "id": e.pk,
            "name": e.full_name,
            "title": e.job_title,
            "department": e.department.name if e.department else "",
            "children": [node(c, seen | {e.pk}) for c in children.get(e.pk, []) if c.pk not in seen],
        }
    

    # Racines : employés sans manager (ou dont le manager n'est plus actif).
    roots = [node(e, set()) for e in employees if e.manager_id is None or e.manager_id not in ids]
    return JsonResponse({"id": 0, "name": "Organisation", "title": "", "department": "", "children": roots})
@login_required
def org_chart(request):
    """Page de l'organigramme : l'arbre est dessiné côté navigateur à partir de l'API JSON."""
    me = request.user.employee_profile
    return render(request, "organization/org_chart.html", {"me_id": me.pk if me else None})