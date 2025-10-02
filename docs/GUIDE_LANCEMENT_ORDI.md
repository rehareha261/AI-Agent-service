Voici un guide rapide pour tester le projet sur un autre ordinateur.

1) Prérequis
- Docker + Docker Compose
- Python 3.12
- Ngrok (optionnel pour webhooks externes)
- Accès aux clés: ANTHROPIC_API_KEY, GITHUB_TOKEN, MONDAY_*, WEBHOOK_SECRET

2) Cloner et installer
- Cloner le repo
- Créer un venv et installer
```bash
git clone <repo_url> && cd AI-Agent
python3.12 -m venv venv && source venv/bin/activate
pip install -U pip && pip install -r requirements.txt
```

3) Configurer l’environnement
- Copier `env_template.txt` en `.env` puis remplir les variables (RabbitMQ, DB, clés API)
```bash
cp env_template.txt .env
# éditez .env (ANTHROPIC_API_KEY, GITHUB_TOKEN, MONDAY_*, WEBHOOK_SECRET, DATABASE_URL, RABBITMQ_*)
```

4) Démarrer l’infra (RabbitMQ/Postgres)
```bash
docker-compose -f docker-compose.rabbitmq.yml up -d
```
docker-compose -f docker-compose.rabbitmq.yml up -d postgres

5) Créer le schéma PostgreSQL
- Appliquer les fichiers SQL (dans cet ordre)
```bash
psql "$DATABASE_URL" -f data/base2.sql
psql "$DATABASE_URL" -f data/view2.sql
psql "$DATABASE_URL" -f data/fonction.sql
```

6) Lancer les services applicatifs
- Backend FastAPI (ex: admin backend)
```bash
uvicorn admin.backend.main:app --reload --host 127.0.0.1 --port 8000
```
- Worker Celery
```bash
celery -A services.celery_app worker --loglevel=info
```

7) Vérifier en local
```bash
curl -i http://127.0.0.1:8000/
curl -i -X POST http://127.0.0.1:8000/webhook/monday -H "Content-Type: application/json" -d '{"ping":"ok"}'
```

8) Exposer via ngrok (si test Monday)
```bash
ngrok http 8000
# Utiliser l’URL https://<subdomain>.ngrok-free.app/webhook/monday
```

9) Test d’intégration “réel” (RabbitMQ)
```bash
python tests/workflow/test_rabbitmq_integration.py --quick --verbose
```

10) Vérifications en base
```bash
<code_block_to_apply_changes_from>
```

11) Dépannage rapide
- 404 sur /webhook/monday: vérifier le chemin exact et utiliser POST.
- 401/403: vérifier la signature (WEBHOOK_SECRET).
- Worker inactif: vérifier RABBITMQ_* et celery_broker_url dans `.env`.
- DB non créée: vérifier `DATABASE_URL` et l’ordre d’exécution des SQL.

C’est tout: après ces étapes, tu peux simuler un webhook (ou le configurer sur Monday) et suivre le flux en temps réel dans les logs Uvicorn et Celery.