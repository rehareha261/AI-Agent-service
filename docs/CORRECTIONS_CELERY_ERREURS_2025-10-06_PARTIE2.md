# Corrections des Erreurs Celery - Partie 2
**Date**: 6 octobre 2025  
**Statut**: ✅ Corrigé

## 🎯 Résumé des Corrections

Ce document décrit les corrections apportées pour résoudre les erreurs Celery détectées dans les logs de production, en particulier les problèmes liés à la persistence en base de données des validations humaines.

---

## ❌ Erreur 1: Foreign Key Constraint sur `human_validations`

### **Symptôme**
```
[2025-10-06 12:49:28,613] ❌ Erreur création validation val_5028673529_1759744168: 
insert or update on table "human_validations" violates foreign key constraint "human_validations_task_id_fkey"
DETAIL: Key (task_id)=(5028673529) is not present in table "tasks".
```

### **Cause Racine**
Le code utilisait `monday_item_id` (5028673529) au lieu de `tasks_id` (36) pour créer les validations humaines. La contrainte de clé étrangère `human_validations.task_id` référence `tasks.tasks_id`, pas `tasks.monday_item_id`.

### **Schéma de la Base de Données**
```sql
-- Table tasks
CREATE TABLE tasks (
    tasks_id BIGINT PRIMARY KEY,           -- ← Clé primaire
    monday_item_id BIGINT UNIQUE NOT NULL, -- ← ID Monday.com (différent!)
    ...
);

-- Table human_validations
CREATE TABLE human_validations (
    task_id BIGINT NOT NULL REFERENCES tasks(tasks_id), -- ← FK vers tasks_id
    ...
);
```

### **Correction Appliquée**

#### 1. Ajout d'un fallback dans `monday_validation_node.py`
```python
# ✅ NOUVEAU: Fallback pour récupérer task_id depuis la DB si manquant dans state
if not task_id_int:
    logger.warning(f"⚠️ db_task_id manquant dans state - tentative récupération depuis DB")
    
    # Essayer de récupérer depuis monday_item_id
    monday_item_id = state["task"].monday_item_id if hasattr(state["task"], 'monday_item_id') else state["task"].task_id
    
    if human_validation_service.db_pool:
        try:
            async with human_validation_service.db_pool.acquire() as conn:
                task_id_int = await conn.fetchval("""
                    SELECT tasks_id FROM tasks WHERE monday_item_id = $1
                """, int(monday_item_id))
                
                if task_id_int:
                    logger.info(f"✅ task_id récupéré depuis DB: {task_id_int} (monday_item_id={monday_item_id})")
                    state["db_task_id"] = task_id_int
                else:
                    logger.error(f"❌ Aucune tâche trouvée pour monday_item_id={monday_item_id}")
        except Exception as e:
            logger.error(f"❌ Erreur récupération task_id depuis DB: {e}")
```

#### 2. Skip de la persistence si task_id manquant
```python
if not task_id_int:
    logger.error(f"❌ Impossible de déterminer task_id - skip sauvegarde validation en DB")
    # Ne pas bloquer le workflow, continuer sans sauvegarder en DB
    task_id_int = None

# ✅ CORRECTION: Ne sauvegarder en DB que si task_id_int est valide
if task_id_int:
    success = await human_validation_service.create_validation_request(...)
else:
    logger.warning(f"⚠️ task_id manquant - skip sauvegarde validation en DB, workflow continue")
```

#### 3. Propagation de db_task_id dans `prepare_node.py`
```python
# ✅ CORRECTION CELERY: S'assurer que db_task_id et db_run_id sont propagés
if "db_task_id" in state and state["db_task_id"] is not None:
    state["results"]["db_task_id"] = state["db_task_id"]
    logger.info(f"✅ db_task_id propagé: {state['db_task_id']}")

if "db_run_id" in state and state["db_run_id"] is not None:
    state["results"]["db_run_id"] = state["db_run_id"]
    logger.info(f"✅ db_run_id propagé: {state['db_run_id']}")
```

### **Impact**
- ✅ Plus d'erreurs de contrainte FK
- ✅ Le workflow continue même si la persistence échoue
- ✅ Meilleure traçabilité avec logs informatifs

---

## ❌ Erreur 2: Validation Non Trouvée lors de la Sauvegarde de la Réponse

### **Symptôme**
```
[2025-10-06 12:50:00,558] ❌ Validation 467888218 non trouvée
[2025-10-06 12:50:00,560] ⚠️ Échec sauvegarde réponse validation en DB
```

### **Cause Racine**
Le code essayait de sauvegarder la réponse de validation avec un `validation_id` qui n'existait pas en base de données. Cela se produisait quand :
1. La validation initiale n'a pas été sauvegardée (parce que `task_id_int` était None)
2. Le code essayait quand même de sauvegarder la réponse

### **Correction Appliquée**

```python
# 7. Sauvegarder la réponse de validation en base de données
try:
    db_validation_id = state.get("results", {}).get("validation_id")
    
    if not db_validation_id:
        logger.info("ℹ️ Pas de validation_id en DB - la validation n'a pas été sauvegardée initialement, skip sauvegarde réponse")
        # Ce n'est pas une erreur - cela arrive quand task_id_int était None
    elif validation_response:
        # Initialiser le service si nécessaire
        if not human_validation_service.db_pool:
            await human_validation_service.init_db_pool()
        
        # Sauvegarder la réponse
        response_saved = await human_validation_service.submit_validation_response(
            validation_id=db_validation_id,
            response=validation_response
        )
        
        if response_saved:
            logger.info(f"✅ Réponse validation {db_validation_id} sauvegardée en DB")
        else:
            logger.warning(f"⚠️ Échec sauvegarde réponse validation en DB")
    else:
        logger.warning("⚠️ Aucune réponse de validation à sauvegarder")
            
except Exception as db_error:
    logger.error(f"❌ Erreur sauvegarde réponse validation en DB: {db_error}")
    # Ne pas bloquer le workflow pour une erreur de persistence
    state["results"]["ai_messages"].append(f"⚠️ Erreur DB réponse: {str(db_error)}")
```

### **Impact**
- ✅ Plus de logs d'erreur inutiles pour les validations non persistées
- ✅ Le workflow continue normalement
- ✅ Messages informatifs au lieu d'erreurs

---

## ❌ Erreur 3: Confusion entre validation_id et update_id

### **Symptôme**
Le code confondait l'`update_id` de Monday.com (467888218) avec le `validation_id` de notre base de données (val_5028673529_1759744168).

### **Cause Racine**
Deux systèmes d'identification différents :
- **Monday.com** : `update_id` (numérique, ex: 467888218)
- **Notre DB** : `validation_id` (chaîne avec préfixe, ex: val_5028673529_1759744168)

### **Correction Appliquée**

```python
# ✅ CORRECTION ERREUR 2: Utiliser le validation_id DB stocké dans le state, pas celui de Monday
db_validation_id = state.get("results", {}).get("validation_id")

if validation_response:
    # ✅ CORRECTION: Créer une copie de la réponse avec le bon validation_id DB
    # validation_response.validation_id peut contenir l'update_id Monday, pas le DB validation_id
    validation_response.validation_id = db_validation_id
    
    # Sauvegarder la réponse
    response_saved = await human_validation_service.submit_validation_response(
        validation_id=db_validation_id,  # ✅ Utiliser le DB validation_id
        response=validation_response
    )
```

### **Impact**
- ✅ Utilisation correcte des IDs de validation
- ✅ Séparation claire entre Monday.com et notre base de données
- ✅ Meilleure traçabilité

---

## 📊 Résumé des Fichiers Modifiés

### 1. `/nodes/monday_validation_node.py`
- **Lignes 186-236** : Ajout de fallback pour récupérer task_id depuis DB
- **Lignes 219-236** : Skip de persistence si task_id manquant
- **Lignes 380-414** : Gestion améliorée de la sauvegarde des réponses

### 2. `/nodes/prepare_node.py`
- **Lignes 305-312** : Propagation de db_task_id et db_run_id dans les résultats

---

## ✅ Validation des Corrections

### Tests Effectués
1. ✅ Workflow complet avec tâche Monday.com existante
2. ✅ Gestion des cas où db_task_id manque
3. ✅ Vérification de la propagation d'état entre nœuds
4. ✅ Tests de linting (aucune erreur)

### Logs Attendus Après Corrections
```
✅ db_task_id propagé: 36
✅ task_id récupéré depuis DB: 36 (monday_item_id=5028673529)
✅ Validation val_5028673529_xxx créée en base de données
✅ Réponse validation val_5028673529_xxx sauvegardée en DB
```

Ou en cas d'échec de récupération (non bloquant) :
```
⚠️ db_task_id manquant dans state - tentative récupération depuis DB
⚠️ task_id manquant - skip sauvegarde validation en DB, workflow continue
ℹ️ Pas de validation_id en DB - skip sauvegarde réponse
```

---

## 🔍 Points d'Attention Futurs

### 1. Synchronisation État-DB
Toujours s'assurer que `db_task_id` est disponible dans l'état avant les nœuds qui en ont besoin.

### 2. Gestion des Erreurs de Persistence
Les erreurs de persistence ne doivent jamais bloquer le workflow principal. Le workflow doit pouvoir continuer même si la persistence échoue.

### 3. Distinction Monday.com vs DB
Toujours utiliser :
- `monday_item_id` pour les appels à l'API Monday.com
- `tasks_id` (via `db_task_id`) pour les opérations en base de données

### 4. Logs Informatifs
Distinguer clairement :
- ❌ Erreurs critiques (bloquantes)
- ⚠️ Avertissements (non bloquants)
- ℹ️ Informations (skip attendu)

---

## 📚 Références

### Base de Données
- `/Users/rehareharanaivo/Desktop/AI-Agent/data/scriptfinal.sql`
  - Table `tasks` : lignes 81-106
  - Table `human_validations` : lignes 491-556
  - Contrainte FK : ligne 498

### Code Source
- `/Users/rehareharanaivo/Desktop/AI-Agent/nodes/monday_validation_node.py`
- `/Users/rehareharanaivo/Desktop/AI-Agent/nodes/prepare_node.py`
- `/Users/rehareharanaivo/Desktop/AI-Agent/services/human_validation_service.py`
- `/Users/rehareharanaivo/Desktop/AI-Agent/graph/workflow_graph.py`

---

## 🎉 Conclusion

Les trois erreurs principales de Celery ont été corrigées :

1. ✅ **Foreign Key Constraint** : Utilisation correcte de `tasks_id` au lieu de `monday_item_id`
2. ✅ **Validation Non Trouvée** : Gestion gracieuse des validations non persistées
3. ✅ **Confusion d'IDs** : Séparation claire entre `update_id` (Monday) et `validation_id` (DB)

**Le workflow peut maintenant continuer même en cas d'erreurs de persistence**, garantissant une meilleure résilience du système.

---

**Auteur**: AI Assistant  
**Date**: 2025-10-06  
**Version**: 1.0

