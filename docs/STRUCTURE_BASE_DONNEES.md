# 📊 STRUCTURE COMPLÈTE DE LA BASE DE DONNÉES AI-AGENT

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Tables principales](#tables-principales)
3. [Relations entre tables](#relations-entre-tables)
4. [Index et performances](#index-et-performances)
5. [Fonctions et triggers](#fonctions-et-triggers)
6. [Vues d'administration](#vues-dadministration)
7. [Guide d'utilisation](#guide-dutilisation)

---

## Vue d'ensemble

### Statistiques du schéma

| Métrique | Valeur |
|----------|--------|
| **Tables principales** | 17 |
| **Vues** | 3 |
| **Fonctions** | 5 |
| **Triggers** | 3 |
| **Index** | 45+ |

### Fichier complet

Le schéma complet combiné est disponible dans :
```
data/schema_complet_ai_agent.sql
```

---

## Tables principales

### 1. Workflow Core (4 tables)

#### 📝 **tasks** - Tâches principales
```sql
tasks_id (PK) ← ID interne DB
monday_item_id (UNIQUE) ← ID Monday.com
```
**Rôle**: Stocke les tâches provenant de Monday.com

**⚠️ IMPORTANT**: 
- `tasks_id` → utilisé pour les foreign keys
- `monday_item_id` → utilisé uniquement pour Monday.com API

#### 🔄 **task_runs** - Exécutions de workflows
```sql
tasks_runs_id (PK)
task_id (FK → tasks.tasks_id)
celery_task_id (UNIQUE)
```
**Rôle**: Une ligne = une exécution de workflow (job Celery)

#### 📍 **run_steps** - Étapes individuelles
```sql
run_steps_id (PK)
task_run_id (FK → task_runs.tasks_runs_id)
node_name ← ex: 'prepare_environment'
```
**Rôle**: Chaque nœud LangGraph du workflow

#### 💾 **run_step_checkpoints** - Points de sauvegarde
```sql
checkpoint_id (PK)
step_id (FK → run_steps.run_steps_id)
```
**Rôle**: Permet la reprise après erreur

---

### 2. IA et Génération (3 tables)

#### 🤖 **ai_interactions** - Historique IA
```sql
ai_interactions_id (PK)
run_step_id (FK)
ai_provider ← 'claude' | 'openai'
token_usage (JSONB)
```
**Rôle**: Chaque appel à une API IA

#### 💻 **ai_code_generations** - Code généré
```sql
ai_code_generations_id (PK)
task_run_id (FK)
generated_code (TEXT)
files_modified (JSONB)
```
**Rôle**: Détails sur le code généré par l'IA

#### 💰 **ai_cost_tracking** - Coûts IA
```sql
ai_cost_tracking_id (PK)
task_id (FK)
cost_usd (NUMERIC)
```
**Rôle**: Tracking des coûts API IA

---

### 3. Validation Humaine (3 tables) ⭐

#### ✋ **human_validations** - Demandes de validation
```sql
human_validations_id (PK)
validation_id (UNIQUE) ← 'val_5028673529_1759744168'
task_id (FK → tasks.tasks_id) ⚠️ IMPORTANT
generated_code (JSONB)
files_modified (TEXT[])
status ← 'pending' | 'approved' | 'rejected' | 'expired'
```

**⚠️ CORRECTION CRITIQUE**:
```python
# ❌ ANCIEN (ERREUR):
task_id = int(state["task"].task_id)  # Monday item ID

# ✅ NOUVEAU (CORRECT):
task_id = state.get("db_task_id")  # DB task ID
```

**Champs importants**:
- `validation_id` → ID unique pour l'application
- `task_id` → FK vers `tasks.tasks_id` (PAS Monday item ID!)
- `generated_code` → JSON string du code généré
- `test_results` → JSON string des résultats de tests
- `pr_info` → JSON string des infos de PR
- `expires_at` → Date limite (défaut: 24h)

#### 👤 **human_validation_responses** - Réponses humaines
```sql
human_validation_responses_id (PK)
human_validation_id (FK → human_validations)
validation_id ← référence croisée
response_status ← 'approved' | 'rejected'
should_merge (BOOLEAN)
```

**⚠️ CORRECTION CRITIQUE**:
```python
# ❌ ANCIEN (ERREUR):
validation_id = validation_response.validation_id  # Update ID Monday

# ✅ NOUVEAU (CORRECT):
validation_id = state["results"]["validation_id"]  # DB validation ID
```

#### 🎬 **validation_actions** - Actions post-validation
```sql
validation_actions_id (PK)
human_validation_id (FK)
action_type ← 'merge_pr' | 'update_monday' | etc.
merge_commit_hash
```

**Rôle**: Actions exécutées après validation (merge, notifications, etc.)

---

### 4. Qualité et Tests (1 table)

#### ✅ **test_results** - Résultats de tests
```sql
test_results_id (PK)
task_run_id (FK)
pytest_report (JSONB)
coverage_percentage
```

---

### 5. GitHub (1 table)

#### 🔀 **pull_requests** - Pull Requests
```sql
pull_requests_id (PK)
task_id (FK → tasks.tasks_id)
github_pr_number
github_pr_url
pr_status ← 'open' | 'merged' | 'closed'
```

---

### 6. Événements et Logs (2 tables)

#### 📬 **webhook_events** - Webhooks entrants
```sql
webhook_events_id (PK)
source ← 'monday' | 'github'
payload (JSONB)
received_at ← PARTITIONNÉ par mois
```

**Partitionnement**:
- `webhook_events_2025_09` (Sept 2025)
- `webhook_events_2025_10` (Oct 2025)
- etc.

#### 📝 **application_logs** - Logs application
```sql
application_logs_id (PK)
level ← 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
source_component
message
```

---

### 7. Monitoring (2 tables)

#### 📊 **performance_metrics** - Métriques de performance
```sql
performance_metrics_id (PK)
task_id (FK)
total_duration_seconds
total_ai_cost
```

#### ⚙️ **system_config** - Configuration système
```sql
system_config_id (PK)
key (UNIQUE)
value (JSONB)
```

---

## Relations entre tables

### Schéma des relations principales

```
tasks (tasks_id)
  ├── task_runs
  │     ├── run_steps
  │     │     ├── run_step_checkpoints
  │     │     └── ai_interactions
  │     ├── ai_code_generations
  │     ├── test_results
  │     └── performance_metrics
  ├── pull_requests
  ├── human_validations ⭐
  │     ├── human_validation_responses
  │     └── validation_actions
  ├── ai_cost_tracking
  └── application_logs
```

### ⚠️ Points d'attention sur les relations

#### 1. **tasks.tasks_id vs monday_item_id**

| ID | Type | Usage |
|----|------|-------|
| `tasks_id` | BIGINT | **Foreign keys DB** |
| `monday_item_id` | BIGINT | **API Monday.com uniquement** |

**Exemple correct**:
```python
# Créer validation
db_task_id = state.get("db_task_id")  # Ex: 36
await create_validation_request(
    validation_request=request,
    task_id=db_task_id  # ✅ Utiliser DB ID, pas Monday item ID
)
```

#### 2. **validation_id mapping**

| ID | Type | Usage |
|----|------|-------|
| `validation_id` (DB) | VARCHAR | **Table human_validations** |
| `update_id` (Monday) | VARCHAR | **API Monday.com uniquement** |

**Exemple correct**:
```python
# Stocker validation_id dans state après création
state["results"]["validation_id"] = "val_5028673529_1759744168"

# Utiliser ce validation_id pour la réponse, PAS l'update_id Monday
db_validation_id = state["results"]["validation_id"]
await submit_validation_response(
    validation_id=db_validation_id  # ✅ DB validation ID
)
```

---

## Index et performances

### Index critiques pour la performance

#### Sur **tasks**
```sql
idx_tasks_monday_item_id (monday_item_id)          ← Lookups Monday
idx_tasks_internal_status_partial (internal_status) ← Queries workflow actifs
```

#### Sur **human_validations** ⭐
```sql
idx_human_validations_validation_id (validation_id)  ← Primary lookup
idx_human_validations_task_id (task_id)              ← Join vers tasks
idx_human_validations_status (status)                ← Filter par statut
idx_human_validations_expires_at (expires_at)        ← Validations urgentes
idx_human_validations_status_expires (status, expires_at) ← Composite
```

#### Sur **task_runs**
```sql
idx_task_runs_celery (celery_task_id)      ← Lookup Celery
idx_task_runs_task_started (task_id, started_at) ← Historique
```

### Stratégie de partitionnement

**webhook_events** est partitionné par mois:
```sql
PARTITION BY RANGE (received_at)
```

**Avantages**:
- Requêtes rapides sur période récente
- Nettoyage simple des anciennes partitions
- Meilleure performance d'insertion

---

## Fonctions et triggers

### Fonctions principales

#### 1. **mark_expired_validations()** → INTEGER
```sql
SELECT mark_expired_validations();
```
**Rôle**: Marque automatiquement les validations expirées
**Retour**: Nombre de validations expirées
**Planification**: À exécuter toutes les 5-10 minutes

#### 2. **sync_validation_status()** → TRIGGER
```sql
-- Trigger automatique sur INSERT human_validation_responses
```
**Rôle**: Met à jour `human_validations.status` automatiquement

#### 3. **get_validation_stats()** → TABLE
```sql
SELECT * FROM get_validation_stats();
```
**Retour**:
- `total_validations`
- `pending_validations`
- `approved_validations`
- `rejected_validations`
- `expired_validations`
- `avg_validation_time_minutes`
- `urgent_validations`

#### 4. **cleanup_old_data()** → VOID
```sql
SELECT cleanup_old_data();
```
**Rôle**: Nettoie les données anciennes
- Webhooks > 6 mois
- Logs > 3 mois
- Validations > 3 mois

#### 5. **trg_touch_updated_at()** → TRIGGER
```sql
-- Trigger automatique sur UPDATE tasks et system_config
```
**Rôle**: Met à jour automatiquement `updated_at`

---

## Vues d'administration

### 1. **validation_dashboard**
```sql
SELECT * FROM validation_dashboard;
```

**Colonnes clés**:
- `is_urgent` → Expire dans < 1h
- `has_test_failures` → Tests ont échoué
- `files_count` → Nombre de fichiers modifiés
- `validation_comments` → Commentaires humains

**Tri**:
1. Pending en premier
2. Urgent en premier
3. Plus récentes en premier

### 2. **validation_history**
```sql
SELECT * FROM validation_history
WHERE validated_by = 'john_doe';
```

**Usage**: Historique complet avec actions de merge

### 3. **workflow_metrics_summary**
```sql
SELECT * FROM workflow_metrics_summary
ORDER BY avg_cost_usd DESC;
```

**Métriques**:
- Nombre total de runs
- Taux de succès
- Coût moyen
- Durée moyenne

---

## Guide d'utilisation

### Installation du schéma

```bash
# 1. Créer la base de données
createdb ai_agent_admin

# 2. Installer le schéma complet
psql -U postgres -d ai_agent_admin -f data/schema_complet_ai_agent.sql

# 3. Vérifier l'installation
psql -U postgres -d ai_agent_admin -c "SELECT * FROM system_config WHERE key = 'schema_version';"
```

### Maintenance régulière

#### Nettoyage hebdomadaire
```sql
-- Exécuter tous les lundis à 2h du matin
SELECT cleanup_old_data();
```

#### Vérification des validations expirées
```sql
-- Exécuter toutes les 10 minutes
SELECT mark_expired_validations();
```

#### Monitoring des performances
```sql
-- Dashboard quotidien
SELECT 
    DATE(recorded_at) as date,
    COUNT(*) as workflows,
    AVG(total_duration_seconds) as avg_duration,
    SUM(total_ai_cost) as total_cost
FROM performance_metrics
WHERE recorded_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(recorded_at)
ORDER BY date DESC;
```

### Requêtes courantes

#### 1. Trouver les validations en attente urgentes
```sql
SELECT * FROM validation_dashboard
WHERE status = 'pending'
  AND is_urgent = TRUE;
```

#### 2. Statistiques de validation par validateur
```sql
SELECT 
    validated_by,
    COUNT(*) as total_validations,
    COUNT(*) FILTER (WHERE response_status = 'approved') as approved,
    COUNT(*) FILTER (WHERE response_status = 'rejected') as rejected,
    AVG(validation_duration_seconds) / 60.0 as avg_minutes
FROM human_validation_responses
WHERE validated_at >= NOW() - INTERVAL '30 days'
GROUP BY validated_by
ORDER BY total_validations DESC;
```

#### 3. Coût IA par provider
```sql
SELECT 
    provider,
    model,
    COUNT(*) as calls,
    SUM(total_tokens) as total_tokens,
    SUM(cost_usd) as total_cost
FROM ai_cost_tracking
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY provider, model
ORDER BY total_cost DESC;
```

#### 4. Workflows les plus lents
```sql
SELECT 
    t.title,
    t.repository_url,
    pm.total_duration_seconds,
    pm.ai_processing_time_seconds,
    pm.testing_time_seconds,
    pm.total_ai_cost
FROM performance_metrics pm
JOIN tasks t ON pm.task_id = t.tasks_id
WHERE pm.recorded_at >= NOW() - INTERVAL '7 days'
ORDER BY pm.total_duration_seconds DESC
LIMIT 10;
```

---

## 📌 Points importants à retenir

### ✅ Bonnes pratiques

1. **Toujours utiliser `db_task_id` pour les foreign keys**
   ```python
   task_id = state.get("db_task_id")  # ✅ CORRECT
   ```

2. **Stocker `validation_id` dans le state**
   ```python
   state["results"]["validation_id"] = validation_id
   ```

3. **Utiliser les vues pour l'administration**
   ```sql
   SELECT * FROM validation_dashboard;  -- Plus simple que des JOINs
   ```

4. **Nettoyer régulièrement les données anciennes**
   ```sql
   SELECT cleanup_old_data();  -- Hebdomadaire
   ```

### ⚠️ Pièges à éviter

1. **❌ NE PAS utiliser `monday_item_id` pour les foreign keys**
   ```python
   # ❌ ERREUR
   task_id = state["task"].task_id  # Monday item ID
   ```

2. **❌ NE PAS utiliser `update_id` Monday comme `validation_id` DB**
   ```python
   # ❌ ERREUR
   validation_id = validation_response.validation_id  # Update ID Monday
   ```

3. **❌ NE PAS oublier de valider la présence de `db_task_id`**
   ```python
   # ✅ TOUJOURS valider
   if not state.get("db_task_id"):
       raise ValueError("db_task_id requis")
   ```

---

## 📚 Ressources additionnelles

- **Schéma complet**: `data/schema_complet_ai_agent.sql`
- **Corrections appliquées**: `docs/CORRECTIONS_CELERY_ERREURS_2025-10-06.md`
- **Documentation validation humaine**: `data/human_validation_migration.sql`
- **Fonctions SQL**: `data/fonction.sql`

---

**Version**: 2.0  
**Date**: 06 Octobre 2025  
**Auteur**: AI-Agent Team

