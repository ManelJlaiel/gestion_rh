from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


@login_required
def home(request):
    """Redirige chaque utilisateur vers l'espace de son rôle."""
    if request.user.is_admin_role:
        return redirect("administration:dashboard")
    # Les espaces Employé, Manager et RH seront ajoutés par les autres modules.
    return render(request, "home.html")
