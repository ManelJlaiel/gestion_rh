from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Sum
from django.shortcuts import render

from accounts.permissions import role_required
from organization.models import ContractType, Employee

User = get_user_model()
admin_or_rh = role_required(User.Role.ADMIN, User.Role.RH)


def _avec_pourcentage(lignes, total):
    """Ajoute à chaque ligne son pourcentage par rapport au total."""
    for ligne in lignes:
        ligne["pct"] = round(ligne["n"] * 100 / total) if total else 0
    return lignes


@admin_or_rh
def dashboard(request):
    actifs = Employee.objects.filter(is_active=True)
    total = actifs.count()

    # Effectif par département (équivalent SQL : GROUP BY department)
    par_departement = _avec_pourcentage(
        list(actifs.values("department__name").annotate(n=Count("id")).order_by("-n")),
        total,
    )

    # Répartition par type de contrat (CDI, CDD, SIVP, Stage)
    noms_contrats = dict(ContractType.choices)
    par_contrat = _avec_pourcentage(
        [
            {"label": noms_contrats.get(l["contract_type"], l["contract_type"]), "n": l["n"]}
            for l in actifs.values("contract_type").annotate(n=Count("id")).order_by("-n")
        ],
        total,
    )

    # Masse salariale et salaire moyen (salaire de base des employés actifs)
    salaires = actifs.aggregate(masse=Sum("base_salary"), moyenne=Avg("base_salary"))

    context = {
        "total": total,
        "inactifs": Employee.objects.filter(is_active=False).count(),
        "masse_salariale": salaires["masse"] or 0,
        "salaire_moyen": salaires["moyenne"] or 0,
        "par_departement": par_departement,
        "par_contrat": par_contrat,
    }
    return render(request, "analytics/dashboard.html", context)