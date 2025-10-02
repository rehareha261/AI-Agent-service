# 🐰 Migration Redis vers RabbitMQ - Architecture AI-Agent

## 🎯 Vue d'ensemble de la Migration

Ce document détaille la migration du broker Redis vers RabbitMQ dans le projet AI-Agent, en conservant toute la fonctionnalité existante tout en améliorant la robustesse et la scalabilité.

## 📊 Comparaison Redis vs RabbitMQ

| Critère | Redis | RabbitMQ | Gagnant |
|---------|-------|----------|------------|
| **Performance** | ⭐⭐⭐⭐⭐ (< 1ms) | ⭐⭐⭐⭐ (< 5ms) | Redis |
| **Fiabilité** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | RabbitMQ |
| **Fonctionnalités Messaging** | ⭐⭐ | ⭐⭐⭐⭐⭐ | RabbitMQ |
| **Monitoring** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | RabbitMQ |
| **Routing Avancé** | ⭐ | ⭐⭐⭐⭐⭐ | RabbitMQ |
| **Dead Letter Queues** | ❌ | ✅ | RabbitMQ |
| **Message TTL** | ⭐⭐ | ⭐⭐⭐⭐⭐ | RabbitMQ |
| **Clustering** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | RabbitMQ |

## 🚀 **Configuration Monday.com OAuth**

### **Nouvelle Méthode d'Authentification**

AI-Agent utilise maintenant l'authentification OAuth Monday.com pour une sécurité renforcée :

#### **1. Création de l'App Monday.com**

1. Rendez-vous sur https://monday.com/developers/apps
2. Cliquez sur "Create App"
3. Configurez votre application :
   - **Name** : "AI-Agent Automation"
   - **Description** : "Agent IA pour automatisation des tâches de développement"

#### **2. Configuration OAuth & Permissions**

Dans l'onglet "OAuth & Permissions" :

```yaml
Scopes requis:
  - boards:read    # Lecture des boards
  - boards:write   # Modification des boards  
  - items:read     # Lecture des items
  - items:write    # Modification des items
  - updates:read   # Lecture des commentaires
  - updates:write  # Ajout de commentaires
```

#### **3. Configuration des Webhooks**

Dans l'onglet "Features" → "Webhooks" :

```yaml
Webhook URL: https://yourdomain.com/webhook/monday
Events à écouter:
  - item_creation
  - change_column_value
  - change_status_column
Webhook Secret: [généré automatiquement]
```

#### **4. Variables d'Environnement**

Ajoutez dans votre `.env` :

```bash
# Monday.com OAuth Configuration
MONDAY_CLIENT_ID=your_client_id_from_app_settings
MONDAY_CLIENT_KEY=your_client_secret_from_app_settings  
MONDAY_APP_ID=your_app_id_from_app_settings

# Monday.com Configuration
MONDAY_BOARD_ID=your_target_board_id
MONDAY_TASK_COLUMN_ID=task_description_column_id
MONDAY_STATUS_COLUMN_ID=status_column_id

# Webhook Security
WEBHOOK_SECRET=your_webhook_secret_from_monday
```

### **Avantages OAuth vs API Key**

| **Aspect** | **API Key (ancienne)** | **OAuth (nouvelle)** |
|------------|----------------------|---------------------|
| **Sécurité** | Token permanent | Token avec expiration |
| **Scopes** | Accès complet | Permissions granulaires |
| **Révocation** | Difficile | Facile depuis l'interface |
| **Audit** | Limité | Logs détaillés |
| **Rate Limiting** | Partagé | Dédié à l'app |

## 📝 Structure des Payloads Webhook Monday.com

### **Payload Type: Changement de Couleur de Bouton**
```json
{
  "event": {
    "pulseId": "1234567890",
    "boardId": "987654321", 
    "pulseName": "Changer la couleur du bouton 'S'inscrire' en #4CAF50",
    "columnValues": {
      "task_type": {"text": "Feature"},
      "priority": {"text": "Medium"},
      "repository_url": {"text": "https://github.com/user/frontend-app"},
      "branch_name": {"text": "feature/green-signup-button"},
      "description": {"text": "Le designer demande de changer la couleur du bouton principal de #007bff (bleu) vers #4CAF50 (vert) pour améliorer la visibilité"}
    },
    "previousColumnValues": {
      "status": {"text": "Backlog"}
    },
    "newColumnValues": {
      "status": {"text": "À faire"}
    }
  },
  "type": "column_value_changed",
  "triggerUuid": "webhook-trigger-123",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### **Payload Type: Feature Complexe**
```json
{
  "event": {
    "pulseId": "2345678901",
    "boardId": "987654321",
    "pulseName": "Implémenter authentification OAuth2 avec Google",
    "columnValues": {
      "task_type": {"text": "Feature"},
      "priority": {"text": "High"},
      "repository_url": {"text": "https://github.com/user/backend-api"},
      "branch_name": {"text": "feature/oauth2-google"},
      "description": {"text": "Ajouter l'authentification OAuth2 avec Google dans l'API backend. Inclure: 1) Endpoint /auth/google 2) Middleware de validation JWT 3) Tests d'intégration 4) Documentation API"},
      "acceptance_criteria": {"text": "- L'utilisateur peut se connecter avec Google\n- JWT valide généré\n- Tests coverage > 90%\n- Documentation Swagger mise à jour"}
    }
  },
  "type": "create_pulse"
}
```

## 🔧 Configuration RabbitMQ

### **1. Variables d'Environnement Mises à Jour**

```bash
# Remplace CELERY_BROKER_URL et CELERY_RESULT_BACKEND
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_VHOST=ai_agent
RABBITMQ_USER=ai_agent_user
RABBITMQ_PASSWORD=secure_password_123

# URL complète pour Celery
CELERY_BROKER_URL=amqp://ai_agent_user:secure_password_123@localhost:5672/ai_agent
CELERY_RESULT_BACKEND=db+postgresql://admin:password@localhost:5432/ai_agent_admin

# Configuration spécifique RabbitMQ
RABBITMQ_MANAGEMENT_PORT=15672
RABBITMQ_ENABLE_MANAGEMENT=true
```

### **2. Docker Compose RabbitMQ**

```yaml
version: '3.8'
services:
  # RabbitMQ remplace Redis
  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    container_name: ai_agent_rabbitmq
    ports:
      - "5672:5672"     # AMQP port
      - "15672:15672"   # Management UI
    environment:
      RABBITMQ_DEFAULT_USER: ai_agent_user
      RABBITMQ_DEFAULT_PASS: secure_password_123
      RABBITMQ_DEFAULT_VHOST: ai_agent
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
      - ./config/rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5
    restart: unless-stopped

  # Application FastAPI
  app:
    build: .
    ports: ["8000:8000"]
    environment:
      - CELERY_BROKER_URL=amqp://ai_agent_user:secure_password_123@rabbitmq:5672/ai_agent
      - CELERY_RESULT_BACKEND=db+postgresql://postgres:5432/ai_agent_admin
    depends_on:
      rabbitmq:
        condition: service_healthy
      postgres:
        condition: service_healthy

  # Workers Celery
  celery-worker:
    build: .
    command: celery -A services.celery_app worker --loglevel=info --queues=webhooks,workflows,ai_generation,tests
    environment:
      - CELERY_BROKER_URL=amqp://ai_agent_user:secure_password_123@rabbitmq:5672/ai_agent
      - CELERY_RESULT_BACKEND=db+postgresql://postgres:5432/ai_agent_admin
    depends_on:
      rabbitmq:
        condition: service_healthy
      postgres:
        condition: service_healthy
    restart: unless-stopped

  # Flower pour monitoring Celery
  celery-flower:
    build: .
    command: celery -A services.celery_app flower --port=5555
    ports: ["5555:5555"]
    environment:
      - CELERY_BROKER_URL=amqp://ai_agent_user:secure_password_123@rabbitmq:5672/ai_agent
      - CELERY_RESULT_BACKEND=db+postgresql://postgres:5432/ai_agent_admin
    depends_on: [rabbitmq, postgres]

volumes:
  rabbitmq_data:
  postgres_data:
```

## 🔀 Mapping des Queues RabbitMQ

### **Queues Spécialisées** :

```python
# Configuration des queues dans Celery
CELERY_TASK_ROUTES = {
    # Webhooks Monday.com (priorité haute)
    'ai_agent_background.process_monday_webhook': {
        'queue': 'webhooks',
        'routing_key': 'webhook.monday',
        'priority': 9
    },
    
    # Workflows LangGraph (priorité normale)
    'ai_agent_background.execute_workflow': {
        'queue': 'workflows', 
        'routing_key': 'workflow.langgraph',
        'priority': 5
    },
    
    # Génération IA (priorité variable selon provider)
    'ai_agent_background.generate_code': {
        'queue': 'ai_generation',
        'routing_key': 'ai.generate.code',
        'priority': 7
    },
    
    # Tests (priorité basse, peut attendre)
    'ai_agent_background.run_tests': {
        'queue': 'tests',
        'routing_key': 'test.execute',
        'priority': 3
    }
}
```

### **Exchanges et Routing** :

```python
# Configuration des exchanges
CELERY_TASK_CREATE_MISSING_QUEUES = True
CELERY_TASK_DEFAULT_EXCHANGE = 'ai_agent'
CELERY_TASK_DEFAULT_EXCHANGE_TYPE = 'topic'
CELERY_TASK_DEFAULT_ROUTING_KEY = 'task.default'

# Déclaration des queues avec options
CELERY_TASK_QUEUES = [
    Queue('webhooks', exchange=Exchange('ai_agent', type='topic'), routing_key='webhook.*'),
    Queue('workflows', exchange=Exchange('ai_agent', type='topic'), routing_key='workflow.*'),
    Queue('ai_generation', exchange=Exchange('ai_agent', type='topic'), routing_key='ai.*'),
    Queue('tests', exchange=Exchange('ai_agent', type='topic'), routing_key='test.*'),
    Queue('dlq', exchange=Exchange('ai_agent', type='topic'), routing_key='dead_letter.*')
]
```

## 💾 Gestion des Résultats

### **Migration Backend Redis → PostgreSQL** :

```python
# Nouvelle configuration Celery
CELERY_RESULT_BACKEND = 'db+postgresql://admin:password@localhost:5432/ai_agent_admin'

# Tables automatiques créées par Celery
# - celery_taskmeta : métadonnées des tâches
# - celery_tasksetmeta : groupes de tâches
```

### **Avantages PostgreSQL Backend** :
- ✅ **Persistance garantie** : Pas de perte de résultats
- ✅ **Requêtes SQL** : Analytics sur les tâches
- ✅ **Backup intégré** : Sauvegarde avec la DB principale
- ✅ **Monitoring unifié** : Même système que les données métier

## 🚨 Dead Letter Queues (DLQ)

### **Configuration DLQ** :
```python
# Auto-routing vers DLQ après échecs
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_ACKS_LATE = True

# Politique de retry avec DLQ
@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60}
)
def process_monday_webhook(self, payload, signature=None):
    try:
        # Logique principale
        pass
    except Exception as exc:
        if self.request.retries >= 3:
            # Envoyer vers DLQ après échecs
            dlq_task = send_to_dead_letter_queue.delay({
                'original_task': 'process_monday_webhook',
                'payload': payload,
                'error': str(exc),
                'retries': self.request.retries
            })
        raise
```

## 📊 Monitoring et Observabilité

### **RabbitMQ Management UI** :
- **URL** : `http://localhost:15672`
- **Login** : `ai_agent_user` / `secure_password_123`
- **Métriques** : Débit, latence, taille des queues, connexions

### **Flower (Celery)** :
- **URL** : `http://localhost:5555`
- **Fonctionnalités** : Statut workers, historique tâches, monitoring temps réel

### **Métriques Clés à Surveiller** :
```python
# Dans monitoring_service.py
async def collect_rabbitmq_metrics():
    """Collecte des métriques RabbitMQ via API Management."""
    metrics = {
        'queue_lengths': await get_queue_lengths(),
        'message_rates': await get_message_rates(),
        'connection_count': await get_active_connections(),
        'consumer_count': await get_consumer_count(),
        'memory_usage': await get_memory_usage()
    }
    return metrics
```

## 🔄 Plan de Migration

### **Phase 1 : Préparation (Jour 1)**
1. ✅ Installer RabbitMQ Docker
2. ✅ Mettre à jour configuration Celery
3. ✅ Tests locaux de connectivité

### **Phase 2 : Adaptation Code (Jour 2-3)**
1. ✅ Modifier `config/settings.py`
2. ✅ Adapter `services/celery_app.py`
3. ✅ Mettre à jour routing des tâches
4. ✅ Implémenter DLQ

### **Phase 3 : Tests (Jour 4)**
1. ✅ Tests unitaires configuration
2. ✅ Tests intégration webhook → RabbitMQ
3. ✅ Tests workflow complet
4. ✅ Tests de charge

### **Phase 4 : Déploiement (Jour 5)**
1. ✅ Migration données si nécessaire
2. ✅ Déploiement production
3. ✅ Monitoring de transition
4. ✅ Rollback plan si nécessaire

## 🎯 Bénéfices Attendus

### **Robustesse** :
- ✅ Messages garantis livrés
- ✅ Retry automatique avec backoff
- ✅ Dead Letter Queue pour débuggage

### **Performance** :
- ✅ Routing intelligent des tâches
- ✅ Priorités natives
- ✅ Load balancing automatique

### **Observabilité** :
- ✅ Dashboard RabbitMQ natif
- ✅ Métriques détaillées
- ✅ Alertes configurables

### **Scalabilité** :
- ✅ Clustering RabbitMQ
- ✅ Workers indépendants
- ✅ Auto-scaling basé sur taille queue

## 🔧 Commandes Utiles

### **Gestion RabbitMQ** :
```bash
# Démarrer RabbitMQ
docker-compose up -d rabbitmq

# Vérifier statut
docker exec ai_agent_rabbitmq rabbitmq-diagnostics status

# Lister queues
docker exec ai_agent_rabbitmq rabbitmqctl list_queues

# Purger une queue
docker exec ai_agent_rabbitmq rabbitmqctl purge_queue webhooks
```

### **Tests Celery** :
```bash
# Démarrer worker
celery -A services.celery_app worker --loglevel=info

# Tester une tâche
python -c "from services.celery_app import process_monday_webhook; process_monday_webhook.delay({'test': 'data'})"

# Monitoring
celery -A services.celery_app flower
```

## 🔒 Sécurité Renforcée

### **Monday.com OAuth Flow**

```python
# 1. Token Acquisition
POST https://auth.monday.com/oauth2/token
{
  "client_id": "your_client_id",
  "client_secret": "your_client_key", 
  "grant_type": "client_credentials",
  "scope": "boards:read boards:write items:read items:write"
}

# 2. API Calls with Bearer Token
POST https://api.monday.com/v2
Headers: {
  "Authorization": "Bearer access_token",
  "Content-Type": "application/json"
}
```

### **Webhook Signature Verification**

```python
import hmac
import hashlib

def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(), 
        payload.encode(), 
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)
```

## 🧪 Tests & Validation

### **Script de Test Intégration**

```bash
# Test complet OAuth + RabbitMQ
python test_rabbitmq_integration.py --oauth-test

# Test des queues RabbitMQ
python test_rabbitmq_integration.py --quick

# Test des webhooks Monday.com
curl -X POST http://localhost:8000/webhook/monday \
  -H "Content-Type: application/json" \
  -H "X-Monday-Signature: $WEBHOOK_SIGNATURE" \
  -d @test_webhook_payload.json
```

## 🎯 Migration Checklist

- [x] ✅ Configuration OAuth Monday.com
- [x] ✅ Migration Redis → RabbitMQ
- [x] ✅ Dead Letter Queues
- [x] ✅ Monitoring intégré
- [x] ✅ Docker Compose production
- [x] ✅ Tests d'intégration
- [x] ✅ Documentation complète
- [x] ✅ Sécurité renforcée

**🎉 Architecture AI-Agent v2.0 avec RabbitMQ et OAuth Monday.com est prête pour la production !** 