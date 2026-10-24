# Gestion RH — projet de départ

Application web de gestion des ressources humaines (Django 5).
Équipe : Eya Ben Youssef, Eya Kouki, Manel Jlaiel, Ghada Sourmri — 4ème année SDIA, TEK-UP.

## Démarrage rapide (sans Docker, base SQLite)

```bash
python -m venv .venv
# Windows : .venv\Scripts\activate    —    Linux/macOS : source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_admin
python manage.py runserver
```

Ouvrir http://127.0.0.1:8000 et se connecter avec `admin` / `Demo2026!`.
Autres comptes de démo : `rh`, `manager`, `employe` (même mot de passe).

## Démarrage avec Docker (PostgreSQL)

```bash
cp .env.example .env
docker compose up --build
docker compose exec web python manage.py seed_admin
```

## Tests

```bash
python manage.py test
```

## Organisation du code

| App | Contenu | Responsable |
|---|---|---|
| `accounts` | Modèle `User` (rôle), décorateur `role_required`, connexion | Eya Ben Youssef |
| `organization` | `Department` (puis `Employee`, `Contract`, `Document`) | Eya Ben Youssef |
| `leaves` | `LeaveType`, `Holiday` (puis `LeaveBalance`, `LeaveRequest`) | Eya Kouki |
| `payroll` | `PayrollRate` (puis `Payslip`, calcul, PDF) | Manel Jlaiel |
| `audit` | `AuditLog` et `log_action()` | Eya Ben Youssef (mécanisme) |
| `administration` | Espace administrateur : tableau de bord, paramètres, comptes, journal d'audit | Manel Jlaiel |
| `templates/base.html` | Layout commun et menu par rôle | Manel Jlaiel |

Les apps `attendance` (Eya Kouki) et `analytics` (Ghada) seront ajoutées par leurs responsables.

## Conventions d'équipe

- Code en anglais, interface en français.
- Une branche `feature/nom-court` par tâche, pull request relue par une autre personne avant le merge.
- On ne modifie pas le modèle d'une autre personne sans la prévenir.
- Chaque vue sensible est protégée par `@role_required(...)`.
- Chaque création, modification ou suppression importante appelle `log_action(...)`.
- Pour ajouter vos liens au menu, complétez le bloc prévu dans `templates/base.html`.

## Points à vérifier

- Les taux CNSS et le barème IRPP créés par `seed_admin` sont indicatifs : vérifiez-les avec la loi de finances en vigueur avant la démo.
- Les jours fériés religieux (dates variables) sont à ajouter chaque année depuis la page Paramètres.
- Bootstrap, Bootstrap Icons et HTMX sont inclus dans `static/vendor/` : l'application fonctionne sans connexion Internet.
