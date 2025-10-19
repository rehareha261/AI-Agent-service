# 🚀 Instructions de Redémarrage - Post Migration

**Date:** 11 octobre 2025  
**Statut:** Configuration mise à jour - Redémarrage requis

---

## ✅ Configuration Terminée

La migration vers le nouveau compte Monday.com est terminée avec succès !

**Nouveau compte :** rehareharanaivo@gmail.com  
**Nouveau board :** 5037922237 (Tâches)

---

## 🔄 Étape 1 : Redémarrer Celery

### Option A : Si Celery tourne dans un terminal

1. **Trouvez le terminal** où Celery est en cours d'exécution
2. **Arrêtez Celery** : Appuyez sur `Ctrl+C`
3. **Attendez** que Celery s'arrête proprement (quelques secondes)
4. **Redémarrez Celery** :

```bash
cd /Users/rehareharanaivo/Desktop/AI-Agent
celery -A services.celery_app worker --loglevel=info
```

### Option B : Si Celery tourne en arrière-plan

```bash
# Trouver le processus Celery
ps aux | grep celery

# Arrêter proprement
pkill -f "celery.*worker"

# Attendre 2-3 secondes

# Redémarrer
cd /Users/rehareharanaivo/Desktop/AI-Agent
celery -A services.celery_app worker --loglevel=info
```

### Vérification du Démarrage

Vous devriez voir ces messages au démarrage :

```
-------------- celery@MacBookPro v5.3.4 (emerald-rush)
--- ***** ----- 
-- ******* ---- macOS-15.6.1-arm64-arm-64bit 2025-10-11 16:XX:XX
...
[INFO] Connected to amqp://ai_agent_user:**@127.0.0.1:5672/ai_agent
[INFO] 🚀 Celery worker prêt
[INFO] ✅ Service de persistence initialisé
```

---

## 🧪 Étape 2 : Créer une Tâche de Test

### 1. Ouvrir Monday.com

Accédez à votre board :  
👉 https://rehareharanaivos-team-company.monday.com/boards/5037922237

### 2. Créer un Nouvel Item

Cliquez sur **"+ Ajouter un élément"** en bas du board

### 3. Remplir les Informations

**Titre de la tâche :**
```
Test AI Agent - Premier test
```

**Repository URL :**
```
https://github.com/votre-username/test-repo
```
*(Remplacez par une vraie URL GitHub si vous en avez une)*

**Statut :**
- Changez le statut de "À faire" vers "Working on it" (ou équivalent)
- C'est ce changement de statut qui déclenche le webhook

### 4. Surveiller les Logs

Dans le terminal où Celery tourne, vous devriez voir :

```bash
[INFO] 📨 Réception d'un webhook Monday.com
[INFO] ✅ Tâche extraite du webhook: Test AI Agent - Premier test
[INFO] 📥 Récupération des détails pour l'item Monday.com: <item_id>
[INFO] 🚀 Lancement workflow pour tâche <task_id>
[INFO] 🔄 Démarrage workflow LangGraph
[INFO] 🚀 Préparation de l'environnement pour: Test AI Agent - Premier test
[INFO] 🔍 Analyse des requirements...
```

---

## ✅ Signes de Succès

### Dans les Logs Celery

✅ Pas d'erreur "Item non trouvé"  
✅ Pas d'erreur "Board non trouvé"  
✅ Le workflow démarre correctement  
✅ Les nœuds s'exécutent (prepare_environment, analyze_requirements, etc.)

### Dans Monday.com

✅ Un commentaire apparaît sur la tâche (update de validation)  
✅ Le statut peut changer automatiquement  
✅ Des updates réguliers sur la progression

### Dans la Base de Données

```bash
# Vérifier que la tâche a été créée
cd /Users/rehareharanaivo/Desktop/AI-Agent
python3 -c "
from config.settings import get_settings
import psycopg2
from urllib.parse import urlparse

settings = get_settings()
parsed = urlparse(settings.database_url)
conn = psycopg2.connect(
    host=parsed.hostname,
    port=parsed.port,
    database=parsed.path[1:],
    user=parsed.username,
    password=parsed.password
)
cursor = conn.cursor()
cursor.execute('SELECT tasks_id, title, monday_board_id, internal_status FROM tasks ORDER BY created_at DESC LIMIT 5')
for row in cursor.fetchall():
    print(f'Task {row[0]}: {row[1]} (Board: {row[2]}, Status: {row[3]})')
cursor.close()
conn.close()
"
```

Vous devriez voir votre tâche avec **Board: 5037922237**

---

## ⚠️ Problèmes Courants

### ❌ Erreur : "Item non trouvé"

**Cause :** L'item a été supprimé juste après la création  
**Solution :** Créez un nouvel item et ne le supprimez pas immédiatement

### ❌ Erreur : "Board non trouvé"

**Cause :** Configuration non rechargée  
**Solution :** 
1. Vérifiez le .env : `cat .env | grep MONDAY_BOARD_ID`
2. Redémarrez Celery complètement

### ❌ Erreur : "Repository URL non trouvée"

**Cause :** URL GitHub manquante ou mal formatée  
**Solution :** 
- Ajoutez une URL valide dans la colonne "Repository URL"
- Format : `https://github.com/username/repo`

### ❌ Aucun webhook reçu

**Cause :** Webhook non configuré sur Monday.com  
**Solution :** 
1. Allez dans Monday.com → Integrations → Webhooks
2. Vérifiez qu'un webhook est configuré pour votre board
3. URL webhook : `<votre-domaine>/webhook/monday`

---

## 🔍 Commandes de Diagnostic

### Vérifier la Configuration

```bash
cd /Users/rehareharanaivo/Desktop/AI-Agent
python3 scripts/fix_monday_config.py
```

### Voir les Dernières Tâches

```bash
cd /Users/rehareharanaivo/Desktop/AI-Agent
python3 -c "
from config.settings import get_settings
import psycopg2
from urllib.parse import urlparse

settings = get_settings()
parsed = urlparse(settings.database_url)
conn = psycopg2.connect(
    host=parsed.hostname, port=parsed.port,
    database=parsed.path[1:], user=parsed.username,
    password=parsed.password
)
cursor = conn.cursor()
cursor.execute('''
    SELECT tasks_id, monday_item_id, title, 
           monday_board_id, internal_status, created_at 
    FROM tasks 
    ORDER BY created_at DESC 
    LIMIT 10
''')
print('\\n📋 Dernières tâches:\\n')
for row in cursor.fetchall():
    print(f'ID: {row[0]:3d} | Monday: {row[1]} | Board: {row[3]} | Status: {row[4]:15s} | {row[2]}')
cursor.close()
conn.close()
"
```

### Vérifier les Logs en Temps Réel

```bash
# Dans un autre terminal
cd /Users/rehareharanaivo/Desktop/AI-Agent
tail -f logs/celery.log
```

---

## ✅ Checklist Finale

Après avoir redémarré Celery et créé une tâche de test :

- [ ] Celery redémarré sans erreur
- [ ] Tâche de test créée dans Monday.com
- [ ] Webhook reçu par Celery (visible dans les logs)
- [ ] Tâche créée en base de données avec board_id=5037922237
- [ ] Workflow démarre (logs montrent les nœuds s'exécutant)
- [ ] Update posté sur Monday.com
- [ ] Aucune erreur "Item non trouvé" ou "Board non trouvé"

---

## 🎉 Succès !

Si tous les points de la checklist sont validés, votre système est **opérationnel** avec le nouveau compte Monday.com !

**Vous pouvez maintenant :**
- Créer de vraies tâches dans Monday.com
- Le système les traitera automatiquement
- Surveiller la progression dans les logs et dans Monday.com

---

**Besoin d'aide ?** Relancez `python3 scripts/fix_monday_config.py` pour un diagnostic complet.

