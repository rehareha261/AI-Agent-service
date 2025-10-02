# 🚀 Quand l'Agent se Déclenche-t-il ?

## 🎯 **Réponse directe à votre question**

**NON, l'agent ne fonctionne pas QUE avec les nouveaux items !** 

Il peut être déclenché par **TOUS les items** (nouveaux ET existants) selon votre configuration.

## 📨 **Types d'événements qui déclenchent l'agent**

### ✅ **Ce qui PEUT déclencher l'agent :**

1. **📝 Création d'un nouvel item** (`create_pulse`)
2. **✏️ Modification d'un item existant** (`update_pulse`) 
3. **🔄 Changement de statut d'un item**
4. **📋 Modification de colonnes spécifiques**

### 🎛️ **Configuration Monday.com Webhook**

Dans Monday.com, vous configurez **quels événements** déclenchent le webhook :

```
Paramètres → Intégrations → Webhooks
└── Événements à surveiller :
    ✅ Item created          ← Nouveaux items
    ✅ Item updated          ← Items existants modifiés
    ✅ Column value changed  ← Changement de colonnes
    ✅ Status changed        ← Changement de statut
```

## 🔄 **Modes de déclenchement pratiques**

### **Mode 1: Nouveaux items uniquement**
```
Configuration webhook Monday.com :
✅ Item created
❌ Item updated
```
→ L'agent ne traite QUE les nouveaux items

### **Mode 2: Items nouveaux ET modifiés**
```
Configuration webhook Monday.com :
✅ Item created
✅ Item updated
```
→ L'agent traite TOUS les items (nouveaux + modifications)

### **Mode 3: Déclenchement sur colonne spécifique**
```
Configuration webhook Monday.com :
✅ Column value changed → Colonne "Statut"
Filtre : Quand statut = "À développer"
```
→ L'agent se déclenche quand vous changez un item vers "À développer"

## 🎯 **Cas d'usage pratiques**

### **Scenario A: Items existants à traiter**

Vous avez 10 items existants dans Monday.com et vous voulez que l'agent les traite :

```bash
# Option 1: Modifier un item existant
1. Ouvrir l'item dans Monday.com
2. Modifier une colonne (ex: description, statut)
3. Sauvegarder
→ Webhook déclenché → Agent activé

# Option 2: Changer le statut
1. Item existant avec statut "En attente"
2. Changer vers "À développer"  
→ Webhook déclenché → Agent activé

# Option 3: API manuelle (sans webhook)
curl -X POST http://localhost:8000/workflow/run \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "ID_ITEM_EXISTANT",
    "title": "Titre item",
    "description": "Description détaillée"
  }'
```

### **Scenario B: Workflow en lot**

Traiter plusieurs items existants d'un coup :

```bash
# Créer un script pour déclencher tous les items
for item_id in "123" "456" "789"; do
  curl -X POST http://localhost:8000/workflow/run \
    -H "Content-Type: application/json" \
    -d "{
      \"task_id\": \"$item_id\",
      \"title\": \"Item $item_id\",
      \"description\": \"Traitement automatique\"
    }"
done
```

## 🛡️ **Protections et filtres**

L'agent a des **protections automatiques** pour éviter les boucles :

### **Protection contre les re-déclenchements**
```python
# L'agent vérifie si l'item a déjà été traité
# (en regardant les commentaires ou le statut)
```

### **Filtre par board**
```python
# Ligne 338 dans monday_tool.py
if board_id != self.settings.monday_board_id:
    return None  # Ignore les autres boards
```

### **Filtre par type d'événement (optionnel)**
Vous pouvez ajouter votre propre filtre :

```python
# Dans monday_tool.py ligne 350
event_type = webhook_data.get("type", "")

# Ajouter cette condition si vous voulez filtrer :
if event_type not in ["create_pulse", "update_pulse"]:
    return None  # Ignore autres événements
```

## 📊 **Configuration recommandée**

### **Pour débuter (sécurisé)**
```
Monday.com webhook :
✅ Item created uniquement

Résultat :
→ Seuls les NOUVEAUX items déclenchent l'agent
→ Pas de risque de traiter des items déjà en cours
```

### **Pour production (complet)**
```
Monday.com webhook :
✅ Item created
✅ Column value changed → Colonne "Statut" → Valeur "À développer"

Résultat :
→ Nouveaux items traités automatiquement
→ Items existants traités quand vous changez le statut
→ Contrôle total sur ce qui est traité
```

### **Pour migration (en lot)**
```
Aucun webhook configuré

Traitement manuel :
→ Script pour traiter tous les items existants
→ Contrôle total du timing
→ Possibilité de tester item par item
```

## 🎯 **Exemple concret**

### **Situation :** Vous avez 50 items existants à traiter

**Option 1 - Webhook sur modification :**
```bash
1. Configurer webhook Monday.com sur "Item updated"
2. Modifier chaque item (ajouter un espace dans la description)
3. L'agent traite automatiquement chaque modification
```

**Option 2 - Webhook sur statut :**
```bash
1. Configurer webhook sur changement de statut
2. Créer un statut "À développer" 
3. Changer le statut des 50 items vers "À développer"
4. L'agent traite automatiquement chaque changement
```

**Option 3 - Traitement manuel :**
```bash
# Script pour traiter tous les items
for item_id in $(cat liste_items.txt); do
  curl -X POST http://localhost:8000/workflow/run \
    -H "Content-Type: application/json" \
    -d "{\"task_id\": \"$item_id\", \"title\": \"Item $item_id\"}"
  sleep 10  # Pause entre chaque traitement
done
```

## ✅ **Résumé**

**L'agent peut traiter :**
- ✅ Nouveaux items (si webhook configuré)
- ✅ Items existants modifiés (si webhook configuré)  
- ✅ Items existants via API manuelle (toujours possible)
- ✅ Items avec changement de statut (si webhook configuré)

**Vous contrôlez via :**
- 🎛️ Configuration des événements webhook Monday.com
- 🔧 Filtres dans le code de l'agent
- 📞 Appels API manuels pour cas spécifiques

**Conseil :** Commencez par "Item created" uniquement, puis ajoutez "Item updated" quand vous êtes à l'aise ! 