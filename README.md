# TriHub — Gestion de séances (Django)

Application Django pour gérer les séances d’un club de triathlon (natation, vélo, course…), avec :

- Modèle unique `Session` (ponctuelle ou récurrente)
- Encadrants (coachs) avec éligibilité par qualifications
- Interface publique (URL par catégorie) : liste, filtres, inscription/désinscription encadrants
- Interface admin Django : création, récurrence, validations

## ⚙️ Stack

- Python 3.12 · Django 5.x
- Base de données : SQLite (développement) / PostgreSQL (production)
- Timezone : Europe/Paris
- Optionnel : Docker + docker-compose (Postgres local)

---

## 🚀 Lancer l’application en local (environnement virtuel)

### Prérequis

- Python ≥ 3.12
- `pip`, `venv`

### Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

### Base de données

Par défaut, l’application utilise **SQLite** (aucune configuration requise).  
Pour utiliser PostgreSQL localement :

```bash
export DB_ENGINE=postgres
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=trihub
export DB_USER=trihub
export DB_PASSWORD=trihub
```

### Migrations et création du super-utilisateur

```bash
python manage.py migrate
python manage.py createsuperuser
```

### Lancer le serveur

```bash
python manage.py runserver
```

- Application : http://127.0.0.1:8000/
- Admin : http://127.0.0.1:8000/admin/
- Liste publique par catégorie : `/public/<category_code>/` (ex. `/public/natation/`)

---

## 🐳 Lancer en Docker local (avec PostgreSQL)

### Prérequis

- Docker Desktop (macOS / Windows) ou Docker Engine (Linux)
- docker-compose

### Fichiers attendus

- `Dockerfile` : image web Django
- `docker-compose.yml` : services `web` + `db`
- `.env.dev` : variables d’environnement du service `web`

Exemple de `.env.dev` :

```env
DJANGO_DEBUG=1
DJANGO_SECRET_KEY=changeme-local
DB_ENGINE=postgres
DB_HOST=db
DB_PORT=5432
DB_NAME=trihub
DB_USER=trihub
DB_PASSWORD=trihub
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
```

### Démarrer

```bash
docker compose up --build -d
```

### Migrations et super-utilisateur

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

### Accès

- Application : http://127.0.0.1:8000/
- Admin : http://127.0.0.1:8000/admin/
- Les données PostgreSQL sont stockées dans le volume Docker `trihub_pgdata`.

---

## 🧠 Configuration dynamique de la base

Le projet choisit automatiquement :

- **SQLite** si aucune variable `DB_HOST` / `DATABASE_URL` n’est définie.
- **PostgreSQL** dès qu’une variable `DB_HOST` ou `DATABASE_URL` existe.

---

## 🌐 Endpoints publics

`/public/<category_code>/` : séances futures de la catégorie (tri chronologique, regroupement par semaine ISO)  
**Filtres disponibles :**

- `?loc=` : lieu
- `?dow=` : jour de la semaine
- `?coach=` : recherche d’un coach inscrit
- `?needs=1` : séances avec manque d’encadrants  
  Inscription/désinscription via pages de confirmation.

---

## 🧰 Commandes utiles

```bash
# Logs containers
docker compose logs -f web
docker compose logs -f db

# Arrêter et supprimer
docker compose down

# (optionnel) supprimer le volume de données Postgres
docker volume rm trihub_pgdata
```

---
