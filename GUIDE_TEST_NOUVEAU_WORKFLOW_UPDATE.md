# 🧪 Guide de Test - Nouveau Workflow depuis Updates Monday

**Date**: 11 octobre 2025  
**Objectif**: Tester le système de déclenchement automatique de workflow depuis des commentaires Monday

---

## 📋 Pré-requis

### 1. Base de données

```bash
# Appliquer la migration SQL
psql -U your_user -d your_database -f data/migration_task_update_triggers.sql
```

### 2. Vérifications avant test

```bash
# Vérifier que les services sont démarrés
# FastAPI doit être en cours d'exécution
# Celery worker doit être en cours d'exécution
```

---

## ✅ Tests Unitaires

### Exécuter les tests

```bash
# Tous les tests
pytest tests/test_update_workflow_trigger.py -v

# Tests spécifiques
pytest tests/test_update_workflow_trigger.py::TestUpdateAnalyzer::test_detect_new_request -v
pytest tests/test_update_workflow_trigger.py::TestUpdateAnalyzer::test_detect_affirmation -v
pytest tests/test_update_workflow_trigger.py::TestUpdateAnalyzer::test_detect_bug_report -v

# Avec couverture
pytest tests/test_update_workflow_trigger.py --cov=services.update_analyzer_service --cov=services.workflow_trigger_service --cov-report=html
```

---

## 🔍 Tests Manuels

### Test 1: Détection d'une nouvelle demande

**Scénario**: Poster un commentaire de nouvelle demande sur une tâche terminée

**Étapes**:
1. Aller sur Monday.com
2. Trouver une tâche avec statut "Done"
3. Poster un commentaire:
   ```
   Bonjour, j'aimerais ajouter un bouton d'export CSV sur la page des utilisateurs
   ```

**Résultats attendus**:
- ✅ Webhook reçu dans FastAPI
- ✅ Update analysé par le LLM
- ✅ Type détecté: `NEW_REQUEST`
- ✅ Confidence > 0.7
- ✅ Nouveau workflow déclenché
- ✅ Nouveau `task_run` créé dans la DB
- ✅ Tâche Celery soumise
- ✅ Commentaire de confirmation posté dans Monday

**Vérifications DB**:
```sql
-- Vérifier le trigger créé
SELECT * FROM task_update_triggers 
ORDER BY created_at DESC LIMIT 1;

-- Vérifier le nouveau run
SELECT * FROM task_runs 
WHERE triggered_by_update_id IS NOT NULL 
ORDER BY started_at DESC LIMIT 1;
```

**Logs attendus**:
```
🔍 Tâche X terminée - analyse du commentaire pour nouveau workflow
📊 Analyse update: type=new_request, requires_workflow=True, confidence=0.92
🚀 Déclenchement d'un nouveau workflow depuis update update_123
✅ Nouveau workflow déclenché: run_id=456, celery_task_id=abc123
```

---

### Test 2: Détection d'une affirmation (pas de workflow)

**Scénario**: Poster un simple remerciement

**Étapes**:
1. Aller sur Monday.com
2. Trouver une tâche avec statut "Done"
3. Poster un commentaire:
   ```
   Merci beaucoup, ça fonctionne parfaitement ! 👍
   ```

**Résultats attendus**:
- ✅ Webhook reçu dans FastAPI
- ✅ Update analysé par le LLM
- ✅ Type détecté: `AFFIRMATION`
- ✅ `requires_workflow = False`
- ❌ Aucun workflow déclenché
- ✅ Trigger enregistré dans la DB avec `triggered_workflow = FALSE`

**Logs attendus**:
```
🔍 Tâche X terminée - analyse du commentaire pour nouveau workflow
📊 Analyse update: type=affirmation, requires_workflow=False, confidence=0.98
ℹ️ Commentaire analysé mais pas de workflow requis: type=affirmation, confidence=0.98
```

---

### Test 3: Détection d'un bug report

**Scénario**: Signaler un bug

**Étapes**:
1. Aller sur Monday.com
2. Trouver une tâche avec statut "Done"
3. Poster un commentaire:
   ```
   Il y a un bug, le bouton ne fonctionne plus sur mobile
   ```

**Résultats attendus**:
- ✅ Type détecté: `BUG_REPORT`
- ✅ `task_type = bugfix` dans les requirements extraits
- ✅ Nouveau workflow déclenché avec priorité élevée

---

### Test 4: Question sans action

**Scénario**: Poser une simple question

**Étapes**:
1. Poster un commentaire:
   ```
   Comment je peux configurer cette feature ?
   ```

**Résultats attendus**:
- ✅ Type détecté: `QUESTION`
- ❌ Aucun workflow déclenché

---

### Test 5: Tâche en cours (pas terminée)

**Scénario**: Poster un commentaire sur une tâche en cours

**Étapes**:
1. Trouver une tâche avec statut "Working on it" ou "In Progress"
2. Poster un commentaire quelconque

**Résultats attendus**:
- ✅ Commentaire enregistré
- ❌ Aucune analyse LLM effectuée
- ❌ Aucun workflow déclenché
- ✅ Log: "Commentaire traité pour tâche en cours"

---

## 🔬 Tests d'Intégration

### Script de test automatisé

Créez un fichier `test_integration_update_workflow.py`:

```python
import asyncio
import httpx
from services.webhook_persistence_service import webhook_persistence

async def test_full_pipeline():
    """Test du pipeline complet."""
    
    # Simuler un webhook Monday.com
    payload = {
        "event": {
            "type": "create_update",
            "pulseId": 12345,
            "textBody": "Ajouter un export CSV",
            "updateId": "test_update_001"
        }
    }
    
    # Traiter le webhook
    result = await webhook_persistence.process_monday_webhook(payload)
    
    print(f"✅ Résultat: {result}")
    
if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
```

---

## 📊 Vérifications en Base de Données

### Statistiques des triggers

```sql
-- Vue des statistiques par type
SELECT * FROM v_update_trigger_stats;

-- Triggers récents
SELECT * FROM v_recent_update_triggers LIMIT 10;

-- Taux de déclenchement
SELECT 
    COUNT(*) AS total_triggers,
    SUM(CASE WHEN requires_workflow THEN 1 ELSE 0 END) AS requires_workflow,
    SUM(CASE WHEN triggered_workflow THEN 1 ELSE 0 END) AS workflows_triggered,
    ROUND(
        100.0 * SUM(CASE WHEN triggered_workflow THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 
        2
    ) AS trigger_rate_percent
FROM task_update_triggers;

-- Confiance moyenne par type
SELECT 
    detected_type,
    AVG(confidence) AS avg_confidence,
    MIN(confidence) AS min_confidence,
    MAX(confidence) AS max_confidence
FROM task_update_triggers
GROUP BY detected_type;
```

### Vérifier l'historique des runs

```sql
-- Runs déclenchés par des updates
SELECT 
    tr.tasks_runs_id,
    tr.status,
    tr.triggered_by_update_id,
    tr.celery_task_id,
    tr.started_at,
    tr.completed_at,
    t.title AS task_title,
    tut.detected_type,
    tut.confidence
FROM task_runs tr
LEFT JOIN tasks t ON tr.task_id = t.tasks_id
LEFT JOIN task_update_triggers tut ON tr.tasks_runs_id = tut.new_run_id
WHERE tr.triggered_by_update_id IS NOT NULL
ORDER BY tr.started_at DESC
LIMIT 10;
```

---

## 🐛 Debugging

### Logs à surveiller

```bash
# Logs FastAPI
tail -f logs/fastapi.log | grep "update"

# Logs Celery
tail -f logs/celery.log | grep "workflow"

# Logs application
tail -f logs/application.log | grep -E "(analyse|trigger|workflow)"
```

### Commandes utiles

```bash
# Vérifier les webhooks reçus
psql -U your_user -d your_database -c "
  SELECT webhook_events_id, event_type, received_at, processed 
  FROM webhook_events 
  WHERE event_type IN ('create_update', 'create_reply') 
  ORDER BY received_at DESC 
  LIMIT 10;
"

# Vérifier les triggers créés
psql -U your_user -d your_database -c "
  SELECT trigger_id, detected_type, confidence, requires_workflow, triggered_workflow 
  FROM task_update_triggers 
  ORDER BY created_at DESC 
  LIMIT 10;
"
```

---

## ⚠️ Problèmes Connus et Solutions

### Problème 1: LLM ne répond pas

**Symptôme**: Timeout ou erreur LLM

**Solution**:
- Vérifier les clés API (ANTHROPIC_API_KEY, OPENAI_API_KEY)
- Vérifier la connexion réseau
- Le système utilise un fallback: en cas d'erreur, aucun workflow n'est déclenché (sécurité)

### Problème 2: Workflow non déclenché malgré une demande claire

**Symptôme**: `requires_workflow = False` alors qu'on attend `True`

**Solutions**:
- Vérifier la confidence (doit être > 0.7)
- Vérifier les logs de l'analyse LLM
- Ajuster le prompt dans `update_analyzer_service.py` si nécessaire

### Problème 3: Table task_update_triggers n'existe pas

**Symptôme**: Erreur SQL "relation does not exist"

**Solution**:
```bash
psql -U your_user -d your_database -f data/migration_task_update_triggers.sql
```

---

## ✅ Checklist de Validation

Avant de considérer le système prêt pour la production:

- [ ] Migration SQL appliquée avec succès
- [ ] Tests unitaires passent (pytest)
- [ ] Test manuel 1 (nouvelle demande) ✅
- [ ] Test manuel 2 (affirmation) ✅
- [ ] Test manuel 3 (bug report) ✅
- [ ] Test manuel 4 (question) ✅
- [ ] Test manuel 5 (tâche en cours) ✅
- [ ] Vérification DB: triggers enregistrés
- [ ] Vérification DB: runs créés
- [ ] Logs clairs et informatifs
- [ ] Commentaires Monday postés correctement
- [ ] Performance acceptable (< 5s pour l'analyse)
- [ ] Pas de faux positifs (affirmations ne déclenchent pas de workflow)
- [ ] Pas de faux négatifs (vraies demandes déclenchent bien un workflow)

---

## 📈 Métriques à Suivre

Après le déploiement, surveiller:

1. **Nombre d'updates analysés** par jour
2. **Taux de déclenchement** (workflows déclenchés / updates analysés)
3. **Confiance moyenne** du LLM
4. **Faux positifs** (workflows déclenchés à tort)
5. **Faux négatifs** (demandes manquées)
6. **Temps de réponse** de l'analyse LLM

```sql
-- Rapport quotidien
SELECT 
    DATE(created_at) AS date,
    COUNT(*) AS total_triggers,
    SUM(CASE WHEN requires_workflow THEN 1 ELSE 0 END) AS requires_workflow,
    SUM(CASE WHEN triggered_workflow THEN 1 ELSE 0 END) AS workflows_triggered,
    AVG(confidence) AS avg_confidence
FROM task_update_triggers
GROUP BY DATE(created_at)
ORDER BY date DESC
LIMIT 7;
```

---

**Bon test ! 🚀**

