# ✅ Checklist de Déploiement - Workflow Update

## 🎯 Objectif
Activer le système de déclenchement automatique de workflows depuis les commentaires Monday.com

---

## ✅ Étapes Complétées (par l'AI)

- [x] Diagnostic du problème (table manquante)
- [x] Correction de la migration SQL (clé étrangère)
- [x] Application de la migration (table créée)
- [x] Ajout des logs de debugging
- [x] Vérification du code (imports, appels)
- [x] Test LLM (analyse d'intent)
- [x] Création des scripts de test

---

## 📋 À Faire Maintenant (par vous)

### ☐ Étape 1: Redémarrer FastAPI

**Pourquoi**: Pour charger les modifications du code (logs debugging)

**Commandes**:
```bash
# Terminal 1: Arrêter FastAPI actuel
pkill -f "uvicorn main:app"

# Terminal 1: Redémarrer
cd /Users/rehareharanaivo/Desktop/AI-Agent
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Vérification**:
```bash
# Terminal 2: Tester que l'API répond
curl http://localhost:8000/health
# Doit retourner: {"status": "ok"}
```

✅ Étape complétée quand FastAPI répond au `/health`

---

### ☐ Étape 2: Configurer Webhook Monday.com

**Pourquoi**: Monday.com doit envoyer les events `create_update`

**Instructions**:
1. Ouvrir Monday.com dans le navigateur
2. Aller dans: **Integrations** → **Webhooks**
3. Trouver votre webhook (URL contenant `/webhooks/monday`)
4. Cliquer sur **Edit** ou **Configure**
5. Dans **Events**, cocher:
   - ✅ `create_pulse`
   - ✅ `update_column_value`
   - ✅ **`create_update`** ← **IMPORTANT**
   - ✅ **`create_reply`** ← **IMPORTANT**
6. Cliquer sur **Save** ou **Update**

**Alternative** (si webhook n'existe pas):
- Créer un nouveau webhook
- URL: `https://votre-domaine.com/webhooks/monday`
- Events: ceux listés ci-dessus

✅ Étape complétée quand `create_update` est coché

---

### ☐ Étape 3: Test Automatique

**Pourquoi**: Vérifier que le système fonctionne avant le test réel

**Commandes**:
```bash
# Terminal 2
cd /Users/rehareharanaivo/Desktop/AI-Agent
python3 test_update_manual.py
```

**Résultat Attendu**:
```
🧪 Test simulation webhook update...
🔔 WEBHOOK UPDATE REÇU: pulse_id=5039108740, text='Bonjour, pouvez-vous ajouter un export CSV ?...'
🔍 Tâche X terminée - analyse du commentaire pour nouveau workflow
📊 Analyse update: type=new_request, requires_workflow=True, confidence=0.95
🚀 Déclenchement d'un nouveau workflow depuis update test_update_manual_001
✅ Nouveau task_run créé: run_id=...
✅ Tâche Celery soumise: task_id=...
```

**Si erreur**:
- Consulter `DIAGNOSTIC_ET_CORRECTIONS.md`
- Vérifier les logs: `tail -f logs/application.log`

✅ Étape complétée quand le test passe sans erreur

---

### ☐ Étape 4: Test Réel Monday.com

**Pourquoi**: Tester en conditions réelles

**Instructions**:

1. **Ouvrir un terminal pour surveiller les logs**:
   ```bash
   tail -f logs/application.log | grep -E '(🔔|analyse|trigger|workflow)'
   ```

2. **Dans Monday.com**:
   - Ouvrir une tâche avec statut **"Done"** ou **"Terminé"**
   - Dans la section **Updates** (commentaires), écrire:
     ```
     Bonjour, pouvez-vous ajouter un export au format CSV ?
     ```
   - Appuyer sur **Envoyer**

3. **Observer les logs** (dans le terminal):
   - ⏱️ Dans les 2-3 secondes, vous devriez voir:
     ```
     🔔 WEBHOOK UPDATE REÇU: pulse_id=..., text='Bonjour, pouvez-vous ajouter...'
     🔍 Tâche X terminée - analyse du commentaire
     📊 Analyse update: type=new_request, confidence=0.95
     🚀 Déclenchement d'un nouveau workflow
     ✅ Nouveau task_run créé
     ```

4. **Vérifier dans Monday.com**:
   - Un nouveau workflow Celery devrait démarrer
   - Un nouveau PR sera créé
   - La tâche Monday sera mise à jour

**Résultat Attendu**:
- Webhook reçu ✅
- Commentaire analysé ✅
- Nouveau workflow lancé ✅
- PR créée automatiquement ✅

✅ Étape complétée quand un workflow démarre depuis le commentaire

---

## 🔍 Diagnostic si Problème

### Cas 1: Aucun log `🔔 WEBHOOK UPDATE REÇU`

**Diagnostic**: Le webhook n'arrive pas

**Solutions**:
1. Vérifier Étape 2: webhook Monday.com configuré ?
2. Vérifier Étape 1: FastAPI tourne ?
   ```bash
   ps aux | grep uvicorn
   ```
3. Vérifier l'URL du webhook dans Monday.com
4. Tester manuellement:
   ```bash
   curl -X POST http://localhost:8000/webhooks/monday \
     -H "Content-Type: application/json" \
     -d '{"event":{"type":"create_update","pulseId":123,"textBody":"Test"}}'
   ```

### Cas 2: Log reçu mais pas d'analyse

**Diagnostic**: La tâche n'est pas "completed"

**Solutions**:
1. Vérifier le statut de la tâche:
   ```sql
   SELECT tasks_id, title, internal_status, monday_status 
   FROM tasks 
   WHERE monday_item_id = VOTRE_PULSE_ID;
   ```
2. Le système analyse seulement les tâches avec `internal_status = 'completed'`
3. Utiliser une tâche vraiment terminée

### Cas 3: Analyse faite mais pas de workflow

**Diagnostic**: Le commentaire n'est pas détecté comme "nouvelle demande"

**Solutions**:
1. Vérifier le log d'analyse:
   ```
   📊 Analyse update: type=affirmation, requires_workflow=False
   ```
2. Reformuler le commentaire plus explicitement:
   - ❌ "Merci !" → détecté comme affirmation
   - ✅ "Pouvez-vous ajouter X ?" → détecté comme nouvelle demande

---

## 📊 Vérification Base de Données

Après un test réussi, vérifier l'enregistrement:

```sql
-- Voir les triggers enregistrés
SELECT * FROM task_update_triggers 
ORDER BY created_at DESC 
LIMIT 5;

-- Voir les workflows lancés depuis updates
SELECT 
    tr.tasks_runs_id,
    tr.tasks_id,
    tr.triggered_by_update_id,
    tr.status,
    t.title
FROM task_runs tr
JOIN tasks t ON tr.tasks_id = t.tasks_id
WHERE tr.triggered_by_update_id IS NOT NULL
ORDER BY tr.created_at DESC
LIMIT 5;
```

---

## 🎉 Critères de Succès Final

Le système fonctionne quand:

- ✅ Un commentaire sur tâche terminée déclenche automatiquement l'analyse
- ✅ Le LLM détecte correctement le type de demande
- ✅ Un nouveau `task_run` est créé
- ✅ Un workflow Celery démarre
- ✅ Un PR est créé automatiquement
- ✅ Monday.com est mis à jour avec le nouveau workflow

---

## 📁 Documentation de Référence

- **Guide complet**: `CORRECTIONS_APPLIQUEES.md`
- **Résumé rapide**: `RESUME_CORRECTIONS.txt`
- **Diagnostic détaillé**: `DIAGNOSTIC_ET_CORRECTIONS.md`
- **Tests**: `test_update_manual.py`

---

## 🚨 Notes Importantes

1. **Seulement sur tâches terminées**: Le système analyse uniquement les commentaires sur des tâches avec statut "Done"/"Completed"

2. **Seuil de confiance**: Le workflow se déclenche si:
   - `type = new_request` (ou modification, bug_report)
   - `confidence > 0.7`

3. **Fallback LLM**: Si Anthropic échoue, le système bascule automatiquement sur OpenAI

4. **Idempotence**: Le même `monday_update_id` ne peut déclencher qu'un seul workflow (contrainte unique)

---

**Version**: 1.0  
**Date**: 11 octobre 2025  
**Statut**: 🟢 Prêt pour déploiement

