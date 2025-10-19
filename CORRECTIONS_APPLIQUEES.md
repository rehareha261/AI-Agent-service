# ✅ Corrections Appliquées - Workflow depuis Updates

**Date**: 11 octobre 2025  
**Statut**: 🟢 PRÊT POUR DÉPLOIEMENT

---

## 📋 Résumé des Corrections

Vous avez signalé que les commentaires ajoutés dans Monday.com sur une tâche terminée ne déclenchaient pas de workflow. Voici toutes les corrections appliquées:

### ✅ Correction 1: Migration SQL Appliquée

**Problème**: La table `task_update_triggers` n'existait pas

**Actions**:
- ✅ Correction de la clé étrangère `webhook_id` (problème de clé composite)
- ✅ Application de la migration via `apply_migration.py`
- ✅ Vérification de la structure: 15 colonnes créées
- ✅ Colonne `triggered_by_update_id` ajoutée à `task_runs`

**Fichiers modifiés**:
- `data/migration_task_update_triggers.sql` (correction FK)

---

### ✅ Correction 2: Logs de Debugging Ajoutés

**Problème**: Pas de visibilité sur la réception des webhooks update

**Actions**:
- ✅ Ajout d'un log au début de `_handle_update_event`
- ✅ Format: `🔔 WEBHOOK UPDATE REÇU: pulse_id=X, text='...', webhook_id=Y`

**Fichiers modifiés**:
- `services/webhook_persistence_service.py` (ligne 190-192)

---

### ✅ Correction 3: Vérifications Système

**Actions**:
- ✅ Vérification du code: imports et appels présents
- ✅ Test LLM: fonctionne avec OpenAI (fallback)
- ✅ Script de test créé: `test_update_manual.py`
- ✅ Script de diagnostic créé: `fix_update_workflow.py`

**Fichiers créés**:
- `apply_migration.py` - Applique la migration SQL
- `check_db_structure.py` - Vérifie la structure DB
- `fix_update_workflow.py` - Diagnostic complet
- `test_update_manual.py` - Test manuel du système
- `DIAGNOSTIC_ET_CORRECTIONS.md` - Guide de diagnostic
- `CORRECTIONS_APPLIQUEES.md` - Ce fichier

---

## 🚀 Déploiement (3 étapes)

### Étape 1: Redémarrer FastAPI

Le code a été modifié, FastAPI doit être redémarré pour prendre en compte:
- Les nouveaux logs de debugging
- Les services update_analyzer et workflow_trigger

```bash
# Trouver le processus FastAPI
ps aux | grep "uvicorn main:app"

# Arrêter
pkill -f "uvicorn main:app"

# Redémarrer
cd /Users/rehareharanaivo/Desktop/AI-Agent
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

### Étape 2: Configurer le Webhook Monday.com

Le webhook Monday.com doit être configuré pour envoyer les events `create_update`.

**Marche à suivre**:

1. Aller sur Monday.com → Integrations → Webhooks
2. Trouver votre webhook (URL: `https://your-domain/webhooks/monday`)
3. Vérifier que les events suivants sont cochés:
   - ✅ `create_pulse` (création d'items)
   - ✅ `update_column_value` (changements de colonnes)
   - ✅ **`create_update`** ← **IMPORTANT: DOIT ÊTRE COCHÉ**
   - ✅ **`create_reply`** ← **IMPORTANT: DOIT ÊTRE COCHÉ**

4. Sauvegarder la configuration

**Vérification**:
```bash
# Dans les logs Monday.com webhook, vous devriez voir:
# Events subscribed: create_pulse, update_column_value, create_update, create_reply
```

---

### Étape 3: Tester le Système

#### Option A: Test Automatique

```bash
cd /Users/rehareharanaivo/Desktop/AI-Agent
python3 test_update_manual.py
```

**Résultat attendu**:
```
🧪 Test simulation webhook update...
🔔 WEBHOOK UPDATE REÇU: pulse_id=5039108740, text='Bonjour, pouvez-vous ajouter un export CSV ?...', webhook_id=X
🔍 Tâche 123 terminée - analyse du commentaire pour nouveau workflow
📊 Analyse update: type=new_request, requires_workflow=True, confidence=0.92
🚀 Déclenchement d'un nouveau workflow depuis update test_update_manual_001
✅ Nouveau workflow déclenché: run_id=456, celery_task_id=abc-123
```

#### Option B: Test Réel Monday.com

1. Aller sur Monday.com
2. Ouvrir une tâche **TERMINÉE** (statut "Done")
3. Ajouter un commentaire dans la section "Updates":
   ```
   Bonjour, pouvez-vous ajouter un export au format CSV ?
   ```

4. Surveiller les logs:
   ```bash
   tail -f logs/application.log | grep -E '(🔔|analyse|trigger|workflow)'
   ```

**Ce que vous devriez voir**:
```
🔔 WEBHOOK UPDATE REÇU: pulse_id=5039108740, text='Bonjour, pouvez-vous ajouter un export au form...', webhook_id=789
🔍 Tâche 123 terminée - analyse du commentaire pour nouveau workflow
📊 Analyse update: type=new_request, requires_workflow=True, confidence=0.95
✅ Trigger enregistré dans la DB: trigger_id=1
🚀 Déclenchement d'un nouveau workflow depuis update monday_update_xyz
✅ Nouveau task_run créé: run_id=456
✅ Tâche Celery soumise: task_id=abc-123-def
```

---

## 🔍 Diagnostic si Ça Ne Marche Pas

### Cas 1: Aucun log `🔔 WEBHOOK UPDATE REÇU`

**Diagnostic**: Le webhook n'est pas reçu

**Solutions**:
1. Vérifier la configuration Monday.com (Étape 2 ci-dessus)
2. Vérifier que FastAPI tourne:
   ```bash
   curl http://localhost:8000/health
   ```
3. Vérifier les logs Monday.com webhook pour voir si l'event est envoyé

### Cas 2: Log reçu mais pas d'analyse

**Diagnostic**: La tâche n'est peut-être pas terminée

**Solutions**:
1. Vérifier le statut de la tâche dans la DB:
   ```python
   # Dans psql ou pgAdmin
   SELECT tasks_id, title, internal_status, monday_status 
   FROM tasks 
   WHERE monday_item_id = 5039108740;
   ```
2. Le système déclenche seulement si `internal_status = 'completed'`
3. Vérifier les logs: `⚠️ Tâche X en statut Y - analyse non déclenchée`

### Cas 3: Analyse faite mais workflow non déclenché

**Diagnostic**: Confidence trop faible ou type incorrect

**Solutions**:
1. Vérifier le log d'analyse:
   ```
   📊 Analyse update: type=affirmation, requires_workflow=False, confidence=0.85
   ```
2. Le workflow se déclenche seulement si:
   - `requires_workflow = True`
   - `confidence > 0.7`
3. Reformuler le commentaire pour être plus explicite:
   ```
   ❌ "Merci beaucoup !" → type=affirmation, pas de workflow
   ✅ "Pouvez-vous ajouter une fonction X ?" → type=new_request, workflow déclenché
   ```

### Cas 4: Erreur LLM

**Diagnostic**: Problème d'API key ou quota

**Solutions**:
1. Vérifier les logs: `ERROR: API call failed`
2. Vérifier les variables d'environnement:
   ```bash
   echo $OPENAI_API_KEY
   echo $ANTHROPIC_API_KEY
   ```
3. Le système utilise un fallback automatique Anthropic → OpenAI

---

## 📊 Vérification dans la Base de Données

Une fois testé, vérifiez que les données sont bien enregistrées:

```sql
-- Voir tous les triggers enregistrés
SELECT 
    trigger_id,
    task_id,
    monday_update_id,
    detected_type,
    confidence,
    requires_workflow,
    triggered_workflow,
    new_run_id,
    created_at
FROM task_update_triggers
ORDER BY created_at DESC
LIMIT 10;

-- Voir les task_runs déclenchés par des updates
SELECT 
    tasks_runs_id,
    tasks_id,
    triggered_by_update_id,
    status,
    created_at
FROM task_runs
WHERE triggered_by_update_id IS NOT NULL
ORDER BY created_at DESC
LIMIT 10;
```

---

## 🎯 Critères de Succès

Après avoir suivi les 3 étapes de déploiement, le système devrait:

✅ **Réception**: Recevoir les webhooks `create_update` de Monday.com  
✅ **Détection**: Identifier automatiquement les tâches terminées  
✅ **Analyse**: Analyser le commentaire avec le LLM  
✅ **Enregistrement**: Enregistrer le trigger dans `task_update_triggers`  
✅ **Déclenchement**: Créer un nouveau `task_run` si nécessaire  
✅ **Exécution**: Lancer le workflow Celery  

---

## 📁 Fichiers Modifiés (Récapitulatif)

### Modifiés
- `data/migration_task_update_triggers.sql` - Correction FK
- `services/webhook_persistence_service.py` - Ajout logs

### Créés (pour diagnostic/test)
- `apply_migration.py`
- `check_db_structure.py`
- `fix_update_workflow.py`
- `test_update_manual.py`
- `DIAGNOSTIC_ET_CORRECTIONS.md`
- `CORRECTIONS_APPLIQUEES.md`

### Existants (implémentation)
- `services/update_analyzer_service.py`
- `services/workflow_trigger_service.py`
- `services/database_persistence_service.py` (méthodes ajoutées)
- `models/schemas.py` (UpdateType, UpdateIntent)
- `tests/test_update_workflow_trigger.py`

---

## 🚨 Important

**Avant de commencer les tests**:
1. ✅ Migration SQL appliquée
2. ⏳ Redémarrer FastAPI (Étape 1)
3. ⏳ Configurer webhook Monday.com (Étape 2)
4. ⏳ Tester (Étape 3)

**Note**: Les étapes 2-3 doivent être faites maintenant pour que le système fonctionne!

---

## 📞 Support

En cas de problème, vérifier dans l'ordre:
1. Logs application: `tail -f logs/application.log`
2. Logs Celery: vérifier les workers
3. DB: table `task_update_triggers`
4. Configuration webhook Monday.com
5. Variables d'environnement API keys

---

**Statut Final**: 🟢 Prêt pour déploiement  
**Prochaine action**: Étape 1 - Redémarrer FastAPI

