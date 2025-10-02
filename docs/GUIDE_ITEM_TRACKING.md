# 🎯 Comment l'Agent Identifie l'Item Monday.com à Mettre à Jour

## 🔄 Processus Automatique - Aucune Configuration Manuelle Requise

L'agent identifie **automatiquement** quel item Monday.com mettre à jour grâce au webhook. Voici le processus complet :

## 📨 1. Réception du Webhook Monday.com

Quand vous créez ou modifiez un item dans Monday.com, le webhook contient automatiquement l'ID de cet item :

```json
{
  "event": {
    "pulseId": "123456789",        ← ID de l'item (clé principale)
    "boardId": "987654321",        ← ID du board
    "pulseName": "Implémenter feature X",
    "columnValues": { ... }
  },
  "type": "create_pulse"
}
```

## 🔍 2. Extraction de l'ID Item

Dans `services/webhook_service.py` :

```python
# 📍 LIGNE 69 : Parsing du webhook
task_info = self.monday_tool.parse_monday_webhook(payload)

# 📍 LIGNE 334 dans monday_tool.py : Extraction de l'ID
item_id = str(event.get("pulseId", ""))  # ← ID extrait ici
```

## 📋 3. Création de la TaskRequest

L'ID est immédiatement assigné à la tâche :

```python
# 📍 LIGNE 175 dans webhook_service.py
task_request = TaskRequest(
    task_id=task_info["item_id"],  # ← ID propagé ici
    title=title,
    description=description,
    # ... autres propriétés
)
```

## 🔄 4. Propagation dans le Workflow

L'ID est accessible dans tout le workflow via `state["task"].task_id` :

```python
# Dans update_monday node (ligne 59)
await monday_tool._arun(
    action="complete_task",
    item_id=task.task_id,  # ← ID utilisé pour la mise à jour
    pr_url=pr_url
)
```

## 🛡️ 5. Sécurités et Validations

### Vérification du Board ID
```python
# Ligne 338 dans monday_tool.py
if board_id != self.settings.monday_board_id:
    logger.info(f"Webhook ignoré - Board ID différent: {board_id}")
    return None  # ← Ignore les items d'autres boards
```

### Configuration .env requise
```env
# L'agent ne traite QUE les items de ce board
MONDAY_BOARD_ID=your_board_id
```

## 🎯 6. Mise à Jour Précise

L'agent met à jour **exactement** l'item qui a déclenché le webhook :

```python
# Types de mises à jour (toutes avec le même item_id)
monday_tool._arun(action="update_item_status", item_id=task.task_id, status="En cours")
monday_tool._arun(action="add_comment", item_id=task.task_id, comment="...")
monday_tool._arun(action="complete_task", item_id=task.task_id, pr_url="...")
```

## 🔗 Exemple Complet de Flux

### 1. Vous créez un item Monday.com
```
📋 Item ID: 123456789
📝 Titre: "Ajouter validation email"
📊 Board: Production Board (ID: 987654321)
```

### 2. Monday.com envoie le webhook
```
POST https://votre-ngrok.ngrok.io/webhook/monday
Body: { "event": { "pulseId": "123456789", ... } }
```

### 3. L'agent extrait l'ID
```
✅ Item ID extrait: 123456789
✅ Board ID vérifié: 987654321
✅ TaskRequest créée avec task_id=123456789
```

### 4. Workflow s'exécute
```
🔄 prepare_environment (task_id: 123456789)
🔄 implement_task (task_id: 123456789)
🔄 run_tests (task_id: 123456789)
🔄 finalize_pr (task_id: 123456789)
🔄 update_monday (item_id: 123456789) ← Mise à jour du bon item
```

### 5. Mise à jour Monday.com
```
✅ Statut mis à jour sur l'item 123456789
✅ Commentaire ajouté à l'item 123456789
✅ Lien PR ajouté à l'item 123456789
```

## ⚠️ Cas d'Erreur Gérés

### Item inexistant
```python
if not item_details["success"]:
    logger.error(f"Impossible de récupérer les détails de l'item {task_info['item_id']}")
    return None  # ← Arrête le processus
```

### Board différent
```python
if board_id != self.settings.monday_board_id:
    logger.info(f"Webhook ignoré - Board ID différent: {board_id}")
    return None  # ← Ignore le webhook
```

### Webhook malformé
```python
item_id = str(event.get("pulseId", ""))
if not item_id:
    return None  # ← Ignore si pas d'ID
```

## 🎛️ Configuration Requise

### Fichier .env
```env
# Board à surveiller (obligatoire)
MONDAY_BOARD_ID=987654321

# Colonne de statut à mettre à jour
MONDAY_STATUS_COLUMN_ID=status

# Autres colonnes personnalisées
MONDAY_TASK_COLUMN_ID=task_description
```

### Monday.com Webhook
```
URL: https://votre-ngrok.ngrok.io/webhook/monday
Événements: "Item created", "Item updated"
Board: Production Board (ID: 987654321)
```

## 🔍 Debug et Monitoring

### Logs pour suivre l'ID
```bash
# Dans les logs de l'application, vous verrez :
📨 Réception d'un webhook Monday.com
📋 Tâche créée: Ajouter validation email (ID: 123456789)
🚀 Lancement du workflow pour la tâche: Ajouter validation email
📝 Mise à jour statut pour item: 123456789
✅ Statut mis à jour avec succès pour item: 123456789
```

### Test manuel
```bash
# Vérifier qu'un item spécifique peut être mis à jour
curl -X POST http://localhost:8000/workflow/run \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "123456789",
    "title": "Test manuel",
    "description": "Test de mise à jour"
  }'
```

## ✅ Résumé

**Vous n'avez RIEN à configurer pour l'identification des items !**

1. ✅ L'ID de l'item est **automatiquement** extrait du webhook Monday.com
2. ✅ L'agent met à jour **uniquement** l'item qui a déclenché le webhook
3. ✅ Les sécurités empêchent les mises à jour d'items d'autres boards
4. ✅ Tout est tracé dans les logs pour le debug

**Le seul prérequis** : Configurer correctement le `MONDAY_BOARD_ID` dans votre `.env` pour limiter le traitement aux items du bon board. 