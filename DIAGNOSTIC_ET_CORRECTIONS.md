# 🔧 Diagnostic et Corrections - Workflow depuis Updates

**Date**: 11 octobre 2025  
**Problème**: Les updates Monday sur tâches terminées ne déclenchent pas de workflow

---

## 🔍 Diagnostic Effectué

### ✅ Ce qui fonctionne

1. **Code en place**: Les modifications du `webhook_persistence_service.py` sont présentes
   - Import `update_analyzer_service` ✓
   - Import `workflow_trigger_service` ✓
   - Logique d'analyse présente ✓

2. **Tests unitaires**: 11/11 tests passent ✓

3. **Workflow principal**: Fonctionne correctement (PR #35 créée et mergée)

### ❌ Problème Identifié

**Le webhook Monday.com pour les updates n'est PAS reçu**

Causes possibles:
1. FastAPI n'a pas été redémarré après les modifications
2. Monday.com webhook pas configuré pour `create_update` events
3. La table `task_update_triggers` n'existe pas (migration non appliquée)

---

## 🔧 Corrections à Appliquer (Une par Une)

### **CORRECTION 1: Appliquer la Migration SQL**

**Problème**: La table `task_update_triggers` n'existe probablement pas

**Solution**:
```bash
# Via l'application (si la DB est accessible)
python3 -c "
from services.database_persistence_service import db_persistence
import asyncio

async def check():
    await db_persistence.initialize()
    async with db_persistence.pool.acquire() as conn:
        exists = await conn.fetchval('''
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'task_update_triggers'
            )
        ''')
        if exists:
            print('✅ Table task_update_triggers existe')
        else:
            print('❌ Table task_update_triggers manquante')
            print('Action: Appliquer la migration SQL')
        
        # Vérifier la colonne
        col_exists = await conn.fetchval('''
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'task_runs' 
                AND column_name = 'triggered_by_update_id'
            )
        ''')
        if col_exists:
            print('✅ Colonne triggered_by_update_id existe')
        else:
            print('❌ Colonne triggered_by_update_id manquante')

asyncio.run(check())
"
```

**Si manquante, appliquer**:
```sql
-- Copier et exécuter le contenu de data/migration_task_update_triggers.sql
-- dans votre client SQL (pgAdmin, psql, etc.)
```

---

### **CORRECTION 2: Vérifier la Configuration Webhook Monday.com**

**Problème**: Monday.com doit être configuré pour envoyer les events `create_update`

**Solution**:

1. Aller sur Monday.com → Integrations → Webhooks
2. Vérifier les events configurés:
   ```
   ✅ create_pulse
   ✅ update_column_value
   ✅ create_update  ← DOIT ÊTRE COCHÉ
   ✅ create_reply   ← DOIT ÊTRE COCHÉ
   ```

3. Si pas configuré, ajouter:
   - Event: `create_update`
   - URL: `https://your-domain/webhooks/monday`

---

### **CORRECTION 3: Redémarrer FastAPI**

**Problème**: FastAPI doit être redémarré pour prendre en compte les modifications

**Solution**:
```bash
# Si en mode dev avec --reload, pas besoin
# Sinon, redémarrer le processus FastAPI

# Trouver le process
ps aux | grep "uvicorn main:app"

# Tuer et relancer
pkill -f "uvicorn main:app"
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

### **CORRECTION 4: Test Manuel du Système**

**Créer un script de test**:

```python
# test_update_detection.py
import asyncio
from services.webhook_persistence_service import webhook_persistence
from services.database_persistence_service import db_persistence

async def test_update_event():
    """Teste la détection d'update sur une tâche terminée."""
    
    await db_persistence.initialize()
    
    # Simuler un webhook create_update
    payload = {
        "event": {
            "type": "create_update",
            "pulseId": 5039108740,  # Remplacer par votre item ID
            "textBody": "Bonjour, pouvez-vous ajouter un export CSV ?",
            "updateId": "test_update_123"
        }
    }
    
    # Traiter
    result = await webhook_persistence.process_monday_webhook(payload)
    
    print(f"Résultat: {result}")

if __name__ == "__main__":
    asyncio.run(test_update_event())
```

**Exécuter**:
```bash
python3 test_update_detection.py
```

**Résultat attendu**:
```
🔍 Tâche X terminée - analyse du commentaire pour nouveau workflow
📊 Analyse update: type=new_request, requires_workflow=True, confidence=0.92
🚀 Déclenchement d'un nouveau workflow depuis update test_update_123
✅ Nouveau workflow déclenché: run_id=..., celery_task_id=...
```

---

### **CORRECTION 5: Ajouter des Logs de Debugging**

**Problème**: Manque de visibilité sur ce qui se passe

**Solution**: Ajouter un log au début de `_handle_update_event`:

```python
# Dans services/webhook_persistence_service.py, ligne ~183

@staticmethod
async def _handle_update_event(payload: Dict[str, Any], webhook_id: int):
    """Traite un événement d'update/commentaire Monday.com."""
    try:
        pulse_id = payload.get("pulseId")
        update_text = payload.get("textBody", "")
        update_id = payload.get("updateId") or payload.get("id") or f"update_{pulse_id}_{webhook_id}"
        
        # ✅ AJOUT: Log de debugging
        logger.info(f"🔔 WEBHOOK UPDATE REÇU: pulse_id={pulse_id}, text='{update_text[:50]}...', webhook_id={webhook_id}")
        
        # ... reste du code
```

---

### **CORRECTION 6: Vérifier le Type d'Event Reçu**

**Problème**: Monday.com pourrait envoyer un type d'event différent

**Solution**: Logger tous les webhooks reçus:

```bash
# Surveiller les logs
tail -f logs/application.log | grep -E "(📨|webhook|update)"
```

**Ensuite, poster un commentaire dans Monday et vérifier**:
- Est-ce qu'un webhook arrive ?
- Quel est le `event_type` ?
- Est-ce `create_update` ou autre chose ?

---

## 📋 Checklist de Correction (À faire dans l'ordre)

- [ ] **1. Vérifier migration SQL**
  ```bash
  python3 validate_update_workflow.py
  ```

- [ ] **2. Vérifier configuration Monday webhook**
  - Aller sur Monday.com → Integrations
  - Vérifier que `create_update` est coché

- [ ] **3. Redémarrer FastAPI**
  ```bash
  # Redémarrer le serveur
  ```

- [ ] **4. Ajouter logs debugging**
  - Modifier `webhook_persistence_service.py`
  - Ajouter le log au début de `_handle_update_event`

- [ ] **5. Tester manuellement**
  - Poster un commentaire dans Monday
  - Vérifier les logs: `tail -f logs/application.log`

- [ ] **6. Vérifier la DB**
  - La table `task_update_triggers` existe ?
  - Des triggers sont enregistrés ?

---

## 🔍 Commandes de Diagnostic

### Vérifier si FastAPI tourne
```bash
curl http://localhost:8000/health || echo "FastAPI ne répond pas"
```

### Vérifier les webhooks reçus
```bash
tail -50 logs/application.log | grep "webhook"
```

### Tester l'analyse LLM manuellement
```python
import asyncio
from services.update_analyzer_service import update_analyzer_service

async def test():
    context = {
        'task_title': 'Test',
        'task_status': 'completed',
        'original_description': 'Test'
    }
    result = await update_analyzer_service.analyze_update_intent(
        'Pouvez-vous ajouter un export CSV ?',
        context
    )
    print(f'Type: {result.type}, Confidence: {result.confidence}')

asyncio.run(test())
```

---

## 🎯 Prochaines Étapes

1. **Appliquer CORRECTION 1**: Vérifier/appliquer migration SQL
2. **Appliquer CORRECTION 2**: Configurer webhook Monday.com  
3. **Appliquer CORRECTION 3**: Redémarrer FastAPI
4. **Appliquer CORRECTION 4**: Tester manuellement
5. **Appliquer CORRECTION 5**: Ajouter logs
6. **Appliquer CORRECTION 6**: Monitorer

---

**Note**: Le code est correct, c'est probablement un problème de:
- Configuration webhook Monday.com (le plus probable)
- Migration SQL non appliquée
- FastAPI pas redémarré

