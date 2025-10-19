# 🔄 RÔLES DE RABBITMQ ET REDIS DANS AI-AGENT

## 📊 Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────┐
│                      ARCHITECTURE AI-AGENT                          │
└─────────────────────────────────────────────────────────────────────┘

        Monday.com Webhook
               │
               ▼
        ┌─────────────┐
        │   FastAPI   │  ← Réception webhook HTTP
        │  (main.py)  │
        └─────────────┘
               │
               │ (1) Envoyer tâche
               ▼
     ┌──────────────────────┐
     │     RabbitMQ         │  ← MESSAGE BROKER (file d'attente)
     │  (Message Broker)    │     Orchestration des tâches
     └──────────────────────┘
               │
               │ (2) Worker récupère
               ▼
        ┌─────────────┐
        │   Celery    │  ← Workers asynchrones
        │   Worker    │     Exécution des workflows
        └─────────────┘
               │
               │ (3) Exécuter workflow
               ▼
     ┌──────────────────────┐
     │   LangGraph          │  ← Workflow IA multi-étapes
     │   Workflow           │     (analyse, code, test, QA)
     └──────────────────────┘
        │            │
        ▼            ▼
   PostgreSQL     Redis (optionnel)
   (Données)      (Cache)
```

---

## 🐰 RabbitMQ - MESSAGE BROKER (ACTUELLEMENT UTILISÉ ✅)

### **Rôle Principal: Orchestration et File d'Attente**

RabbitMQ gère la **communication asynchrone** entre vos composants.

### 🎯 Responsabilités dans AI-Agent

#### 1. **Recevoir les Tâches des Webhooks**
```python
# Flux: Monday.com → FastAPI → RabbitMQ

# 1. Webhook Monday reçu par FastAPI
@app.post("/webhook/monday")
async def receive_webhook(payload):
    task_data = extract_task_info(payload)
    
    # 2. Envoyer à RabbitMQ via Celery
    celery_task_id = celery_app.send_task(
        'process_monday_webhook',
        args=[task_data],
        queue='webhooks',       # ← Queue RabbitMQ spécialisée
        priority=7              # ← Priorité haute
    )
    
    return {"status": "queued", "celery_task_id": celery_task_id}
```

**Configuration RabbitMQ dans votre projet:**
```yaml
# docker-compose.rabbitmq.yml
rabbitmq:
  image: rabbitmq:3.12-management-alpine
  ports:
    - "5672:5672"      # Port AMQP (protocole de messages)
    - "15672:15672"    # Interface web management
  environment:
    RABBITMQ_DEFAULT_USER: ai_agent_user
    RABBITMQ_DEFAULT_PASS: secure_password_123
    RABBITMQ_DEFAULT_VHOST: ai_agent
```

#### 2. **Gérer 3 Queues Spécialisées**
```python
# services/celery_app.py (lignes 78-108)

task_queues=[
    # Queue 1: Webhooks (priorité haute)
    Queue('webhooks',
          routing_key='webhook.*',
          queue_arguments={
              'x-max-priority': 10,           # Priorité 0-10
              'x-message-ttl': 900000,        # TTL: 15 minutes
              'x-dead-letter-exchange': '...' # Gestion erreurs
          }),
    
    # Queue 2: Workflows LangGraph (priorité normale)
    Queue('workflows',
          routing_key='workflow.*',
          queue_arguments={
              'x-max-priority': 5,
              'x-message-ttl': 3600000,       # TTL: 1 heure
          }),
    
    # Queue 3: Génération IA (priorité basse)
    Queue('ai_generation', ...)
]
```

**Signification:**
- **webhooks** : Traiter les événements Monday.com rapidement (< 5 secondes)
- **workflows** : Exécuter workflows LangGraph longs (5-15 minutes)
- **ai_generation** : Générations IA intensives (code, tests)

#### 3. **Distribution aux Workers Celery**
```bash
# Vous avez 2 workers spécialisés (docker-compose.rabbitmq.yml lignes 136-210)

# Worker 1: Traitement webhooks (4 processus concurrents)
celery-worker-webhooks:
  command: celery -A services.celery_app worker 
           --queues=webhooks 
           --concurrency=4
  
# Worker 2: Exécution workflows (2 processus)
celery-worker-workflows:
  command: celery -A services.celery_app worker 
           --queues=workflows 
           --concurrency=2
```

**Pourquoi 2 workers séparés ?**
- Isolation : Un workflow lent ne bloque pas les webhooks
- Scaling : Ajuster concurrence selon la charge
- Fiabilité : Si un worker crash, l'autre continue

#### 4. **Retry Automatique et Dead Letter**
```python
# services/celery_app.py

# Configuration retry
task_max_retries=3,
task_default_retry_delay=60,  # 1 minute entre retries

# Dead Letter Queue (DLQ)
'x-dead-letter-exchange': 'ai_agent'
'x-dead-letter-routing-key': 'dead_letter.workflow'
```

**Comportement:**
1. Tâche échoue → Retry après 1 minute (max 3 fois)
2. Si échec définitif → Envoi vers Dead Letter Queue
3. DLQ permet analyse post-mortem sans perdre données

---

## 🎯 Cas d'Usage Concrets RabbitMQ

### **Scénario 1: Webhook Monday.com reçu**
```
T+0ms    : Monday → FastAPI reçoit webhook
T+50ms   : FastAPI → Envoie message à RabbitMQ queue 'webhooks'
T+100ms  : RabbitMQ → Distribue à celery-worker-webhooks
T+150ms  : Worker démarre traitement
T+3000ms : Traitement terminé, résultat sauvegardé en DB
```

**Sans RabbitMQ:** FastAPI bloquerait pendant 3 secondes → timeout webhook Monday

**Avec RabbitMQ:** FastAPI répond en 50ms → webhook OK, traitement asynchrone

### **Scénario 2: 10 Webhooks simultanés**
```
RabbitMQ Queue 'webhooks':
┌────────────────────────────────┐
│ [Task 1] [Task 2] [Task 3] ... │  ← File d'attente FIFO
└────────────────────────────────┘
        │
        ▼ Distribution automatique
┌──────────┬──────────┬──────────┬──────────┐
│ Worker 1 │ Worker 2 │ Worker 3 │ Worker 4 │
└──────────┴──────────┴──────────┴──────────┘
  Traite     Traite     Traite     Traite
  Task 1     Task 2     Task 3     Task 4
```

**Avantages:**
- Pas de surcharge : Maximum 4 workflows en parallèle
- Pas de perte : Tasks 5-10 attendent dans la queue
- Fair processing : FIFO garantit ordre

### **Scénario 3: Worker Crash**
```
Avant crash:
Worker 1 traite Task A (acknowledgement pas encore envoyé)
         ↓
Crash! Worker 1 meurt
         ↓
RabbitMQ détecte absence acknowledgement
         ↓
RabbitMQ ré-envoie Task A à Worker 2
         ↓
Task A complétée avec succès
```

**Protection:** `task_acks_late=True` (ligne 64)

---

## 🔴 Redis - CACHE (PROPOSITION, NON IMPLÉMENTÉ ACTUELLEMENT ⚠️)

### **Rôle Principal: Cache Haute Performance**

Redis servirait à **stocker temporairement** des résultats coûteux.

### 🎯 Utilité Proposée pour AI-Agent

#### 1. **Cacher Résultats LLM Répétitifs**

**Problème actuel:**
```python
# Scenario: 3 tâches sur le même repo GitHub

Task 1: Analyser structure de "myapp" → Appel Claude ($0.15, 5s)
Task 2: Analyser structure de "myapp" → Appel Claude ($0.15, 5s) ❌ REDONDANT
Task 3: Analyser structure de "myapp" → Appel Claude ($0.15, 5s) ❌ REDONDANT

Coût total: $0.45 + 15 secondes
```

**Solution avec Redis:**
```python
import redis
from functools import wraps

redis_client = redis.Redis(host='localhost', port=6379)

def cache_result(ttl=1800):  # 30 minutes
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Créer clé unique basée sur arguments
            cache_key = f"{func.__name__}:{hash((args, str(kwargs)))}"
            
            # Vérifier cache
            cached = redis_client.get(cache_key)
            if cached:
                logger.info(f"✅ Cache HIT: {cache_key}")
                return json.loads(cached)
            
            # Cache MISS → Appeler LLM
            logger.info(f"❌ Cache MISS: {cache_key}")
            result = await func(*args, **kwargs)
            
            # Stocker en cache (TTL: 30 min)
            redis_client.setex(cache_key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator

# Application dans votre code
@cache_result(ttl=1800)
async def detect_project_with_llm(repo_url: str):
    """Détection type de projet (Python/JS/etc.)"""
    response = await claude.analyze(repo_url)
    return response

# Résultat avec cache
Task 1: Analyser "myapp" → Appel Claude ($0.15, 5s)  → Stocké en Redis
Task 2: Analyser "myapp" → Redis HIT ($0.00, 10ms) ✅ -99% temps
Task 3: Analyser "myapp" → Redis HIT ($0.00, 10ms) ✅ -99% temps

Coût total: $0.15 + 5 secondes (économie: $0.30 + 10s)
```

#### 2. **Pub/Sub pour Webhooks Temps Réel**

**Problème actuel (Validation Humaine Monday.com):**
```python
# nodes/monday_validation_node.py

async def wait_for_human_reply(update_id):
    """Polling actif toutes les 5 secondes."""
    while True:
        # ❌ Appel API Monday.com
        replies = await monday_api.get_replies(update_id)
        if replies:
            return replies[0]
        
        await asyncio.sleep(5)  # Attendre 5s
        # Répéter toutes les 5s pendant 10 minutes = 120 appels API!
```

**Solution avec Redis Pub/Sub:**
```python
# Récepteur webhook (main.py)
@app.post("/webhook/monday/reply")
async def handle_reply(payload):
    update_id = payload['pulseId']
    reply_text = payload['textBody']
    
    # ✅ Publier sur canal Redis
    redis_client.publish(f'monday:reply:{update_id}', reply_text)
    return {"status": "ok"}

# Attente dans workflow (monday_validation_node.py)
async def wait_for_human_reply(update_id):
    """Attente event-driven."""
    pubsub = redis_client.pubsub()
    pubsub.subscribe(f'monday:reply:{update_id}')
    
    # ✅ Bloquant jusqu'à message (0 polling)
    for message in pubsub.listen():
        if message['type'] == 'message':
            return message['data']
    
    # Latence: <500ms au lieu de 5s minimum
```

**Gains:**
- 0 requêtes API pendant l'attente (au lieu de 120)
- Latence <500ms (au lieu de 5s)
- Pas de rate limiting Monday.com

#### 3. **Stockage Sessions Utilisateur**

```python
# Conversations multi-tours avec l'IA
redis_client.setex(
    f'conversation:{task_id}',
    3600,  # 1 heure
    json.dumps({
        'messages': [...],
        'context': {...}
    })
)
```

---

## 📊 Comparaison Technique

| Critère | RabbitMQ | Redis |
|---------|----------|-------|
| **Type** | Message Broker | Cache In-Memory |
| **Rôle** | Orchestration tâches | Stockage temporaire |
| **Latence** | 10-50ms | <1ms |
| **Persistance** | ✅ Durable | ⚠️ Volatile (option persist) |
| **Garanties** | At-least-once delivery | Best-effort |
| **Usage AI-Agent** | Queue workflows | Cache résultats LLM |
| **Complexité** | Moyenne | Faible |
| **Obligatoire** | ✅ OUI | ⚠️ Optionnel |

---

## 🔄 Ils se Complètent, Ne se Remplacent Pas

### **RabbitMQ** (Obligatoire)
```
Problème résolu: Comment distribuer le travail entre workers ?
Réponse: File d'attente persistante avec retry automatique

Use case:
- Webhook Monday → Task → RabbitMQ → Worker Celery
- Garantie: Message pas perdu même si worker crash
```

### **Redis** (Optionnel mais recommandé)
```
Problème résolu: Comment éviter calculs répétitifs coûteux ?
Réponse: Cache en mémoire ultra-rapide

Use case:
- Analyser même repo 3× → 1 appel LLM + 2 cache hits
- Économie: 67% coût IA, 90% temps
```

---

## 💼 Workflow Complet avec les Deux

```python
# 1. Monday webhook arrive
@app.post("/webhook/monday")
async def receive_webhook(payload):
    # ↓ RabbitMQ: Envoyer tâche asynchrone
    celery_app.send_task('process_monday_webhook', 
                         args=[payload], 
                         queue='webhooks')

# 2. Worker Celery traite
@celery_app.task
def process_monday_webhook(payload):
    task_id = create_task_in_db(payload)
    
    # ↓ RabbitMQ: Envoyer workflow
    celery_app.send_task('execute_workflow', 
                         args=[task_id], 
                         queue='workflows')

# 3. Workflow LangGraph exécuté
async def analyze_node(state):
    repo_url = state['repository_url']
    
    # ↓ Redis: Check cache avant appel LLM
    @cache_result(ttl=1800)
    async def detect_language(url):
        return await llm.analyze(url)  # Coûteux
    
    language = await detect_language(repo_url)
    return {'language': language}
```

**Flux complet:**
```
Monday → FastAPI → [RabbitMQ Queue] → Celery Worker → LangGraph
                                                          ↓
                                                      [Redis Cache]
                                                          ↓
                                                        LLM API
```

---

## 🎯 Recommandation Finale

### **Pour votre projet AI-Agent**

#### ✅ **RabbitMQ** - INDISPENSABLE
**Conservez absolument.** Il est le cœur de votre architecture asynchrone.

**Raisons:**
1. ✅ Déjà configuré et fonctionnel
2. ✅ Gère 3 queues spécialisées
3. ✅ Workers Celery dépendent de lui
4. ✅ Retry automatique + Dead Letter Queue
5. ✅ Scaling horizontal (ajout workers facile)

**Coût:** Négligeable (~50MB RAM)

---

#### 🟡 **Redis** - FORTEMENT RECOMMANDÉ (optionnel)

**Ajoutez-le pour gains immédiats.**

**Impact attendu:**
- 💰 **-40% coûts IA** (cache hits évitent appels LLM)
- ⚡ **-60% latence** analyse répétée (10ms vs 5s)
- 📉 **-90% polling** Monday.com (pub/sub au lieu de polling)

**Coût:** Très faible (~128MB RAM, configuration 10 minutes)

**Configuration minimale:**
```yaml
# Ajouter dans docker-compose.rabbitmq.yml
redis:
  image: redis:7-alpine
  container_name: ai_agent_redis
  ports:
    - "6379:6379"
  command: redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru
  volumes:
    - redis_data:/data
```

---

## 📈 Metrics avec/sans Redis

| Métrique | Sans Redis | Avec Redis | Gain |
|----------|-----------|-----------|------|
| Analyse repo (même repo 3×) | $0.45, 15s | $0.15, 5s | -67% coût, -67% temps |
| Polling Monday validation | 120 req/10min | 0 req | -100% requêtes |
| Latence validation | 5s min | <500ms | -90% latence |
| Cache hit ratio | 0% | 60-70% | Nouveau |
| Coût workflow moyen | $0.60 | $0.35 | -42% |

---

## 🚀 Prochaines Étapes

### Si vous gardez seulement RabbitMQ ✅
```bash
# Votre architecture actuelle fonctionne bien
docker-compose -f docker-compose.rabbitmq.yml up -d

# Accessible:
# - RabbitMQ Management: http://localhost:15672
# - Credentials: ai_agent_user / secure_password_123
```

### Si vous ajoutez Redis 🎯
```bash
# 1. Ajouter service Redis (voir config ci-dessus)
# 2. Installer client Python
pip install redis

# 3. Créer service cache (10 lignes)
# 4. Décorer fonctions coûteuses avec @cache_result()

# Temps d'implémentation: 2-3 heures
# ROI: Immédiat (-40% coûts dès première tâche répétée)
```

---

## 📚 Ressources

**RabbitMQ:**
- Management UI: http://localhost:15672
- Documentation: https://www.rabbitmq.com/documentation.html
- Votre config: `docker-compose.rabbitmq.yml` (lignes 7-39)

**Redis (si ajouté):**
- Redis CLI: `redis-cli`
- Documentation: https://redis.io/docs/
- Python client: https://redis-py.readthedocs.io/

**Monitoring:**
- RabbitMQ queues: `rabbitmqctl list_queues`
- Redis stats: `redis-cli INFO stats`

---

**Conclusion:** RabbitMQ = orchestration (obligatoire), Redis = optimisation (fortement recommandé).
Les deux ensemble forment une architecture moderne et performante. 🚀
