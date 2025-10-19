# ✅ Stockage des Deux URLs de PR en Base de Données

## Résumé

Le système stocke maintenant **les deux URLs de Pull Request** dans la table `task_runs` :

1. **`pull_request_url`** : URL de la PR créée par le workflow
2. **`last_merged_pr_url`** : URL de la dernière PR fusionnée récupérée depuis GitHub

---

## 📊 Structure de la base de données

### Table `task_runs`

```sql
CREATE TABLE task_runs (
    ...
    pull_request_url VARCHAR(500),        -- URL de la PR créée par le workflow
    last_merged_pr_url VARCHAR(500),      -- URL de la dernière PR fusionnée depuis GitHub  
    ...
);
```

### Index créé

```sql
CREATE INDEX idx_task_runs_last_merged_pr_url 
ON task_runs(last_merged_pr_url) 
WHERE last_merged_pr_url IS NOT NULL;
```

---

## 🔄 Flux de sauvegarde

### 1. PR créée par le workflow
```
finalize_pr node
    ↓
create_pull_request (GitHub)
    ↓
db_persistence.create_pull_request()
    ↓
UPDATE task_runs SET pull_request_url = '...'
```

### 2. Dernière PR fusionnée depuis GitHub
```
update_monday node
    ↓
_update_repository_url_column()
    ↓
github_pr_service.get_last_merged_pr()
    ↓
_save_last_merged_pr_to_database()
    ↓
db_persistence.update_last_merged_pr_url()
    ↓
UPDATE task_runs SET last_merged_pr_url = '...'
```

---

## 📁 Fichiers modifiés

### 1. Migration SQL
**Fichier** : `data/add_last_merged_pr_url.sql`
```sql
ALTER TABLE task_runs 
ADD COLUMN IF NOT EXISTS last_merged_pr_url VARCHAR(500);
```

### 2. Service de persistence
**Fichier** : `services/database_persistence_service.py`

**Nouvelle méthode** :
```python
async def update_last_merged_pr_url(
    self, 
    task_run_id: int, 
    last_merged_pr_url: str
):
    """Met à jour l'URL de la dernière PR fusionnée."""
    ...
```

### 3. Node update_monday
**Fichier** : `nodes/update_node.py`

**Nouvelle fonction** :
```python
async def _save_last_merged_pr_to_database(
    state: GraphState, 
    last_merged_pr_url: str
) -> bool:
    """Sauvegarde l'URL en base de données."""
    ...
```

**Modification** :
```python
# Dans _update_repository_url_column()
if update_result and update_result.get("success"):
    # ✅ NOUVEAU: Sauvegarder l'URL en base de données
    await _save_last_merged_pr_to_database(state, pr_url)
    ...
```

---

## ✅ Tests

### Test d'intégration complet

**Fichier** : `tests/test_save_both_pr_urls.py`

**Résultat** : ✅ PASSÉ

```
=== RESULTATS ===

  PR creee par workflow:
    https://github.com/python/cpython/pull/12345

  Derniere PR fusionnee GitHub:
    https://github.com/python/cpython/pull/139294

✅ SUCCES - Les deux URLs sont stockees en base
```

---

## 🎯 Utilisation

### Requête SQL pour voir les deux URLs

```sql
SELECT 
    tasks_runs_id,
    pull_request_url,
    last_merged_pr_url,
    status,
    completed_at
FROM task_runs
WHERE pull_request_url IS NOT NULL 
   OR last_merged_pr_url IS NOT NULL
ORDER BY started_at DESC
LIMIT 10;
```

### Depuis Python

```python
from services.database_persistence_service import db_persistence

# Initialiser
await db_persistence.initialize()

# Récupérer les URLs d'un task_run
async with db_persistence.pool.acquire() as conn:
    result = await conn.fetchrow("""
        SELECT 
            pull_request_url,
            last_merged_pr_url
        FROM task_runs
        WHERE tasks_runs_id = $1
    """, task_run_id)
    
    print(f"PR créée: {result['pull_request_url']}")
    print(f"Dernière PR fusionnée: {result['last_merged_pr_url']}")
```

---

## 🔍 Vérification

### Vérifier que la colonne existe

```bash
python3 -c "
import asyncio
import asyncpg
from config.settings import get_settings

async def check():
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)
    
    result = await conn.fetchval('''
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_name = 'task_runs' 
        AND column_name = 'last_merged_pr_url'
    ''')
    
    print(f'Colonne last_merged_pr_url: {\"✅ Existe\" if result > 0 else \"❌ N\\'existe pas\"}')
    await conn.close()

asyncio.run(check())
"
```

### Tester la sauvegarde

```bash
python3 tests/test_save_both_pr_urls.py
```

---

## 📋 Checklist de migration

- [x] Migration SQL créée (`data/add_last_merged_pr_url.sql`)
- [x] Migration appliquée en base de données
- [x] Colonne `last_merged_pr_url` créée
- [x] Index créé pour optimisation
- [x] Méthode `update_last_merged_pr_url()` implémentée
- [x] Fonction `_save_last_merged_pr_to_database()` implémentée
- [x] Intégration dans `_update_repository_url_column()`
- [x] Test d'intégration créé
- [x] Test passant avec succès
- [x] Documentation complète

---

## 💡 Avantages

### 1. Traçabilité complète
- **PR créée** : Suivi du travail de l'agent IA
- **PR fusionnée** : État actuel du repository

### 2. Historique
- Toutes les URLs sont conservées
- Possibilité d'analyser l'historique des PRs

### 3. Analyses possibles
```sql
-- Comparer le nombre de PRs créées vs fusionnées
SELECT 
    COUNT(DISTINCT pull_request_url) as prs_creees,
    COUNT(DISTINCT last_merged_pr_url) as prs_fusionnees
FROM task_runs;

-- Voir les workflows avec PRs créées mais pas fusionnées
SELECT * FROM task_runs
WHERE pull_request_url IS NOT NULL
  AND last_merged_pr_url IS NULL;
```

---

## 🚀 Exemple de workflow complet

```
1. Workflow démarre
   └─> db_persistence.start_task_run()
   
2. Préparation environnement
   └─> Clone repository depuis state["task"].repository_url
   
3. Implémentation + Tests
   
4. Finalisation
   └─> db_persistence.create_pull_request()
       └─> Sauvegarde pull_request_url = "https://github.com/owner/repo/pull/123"
   
5. Mise à jour Monday
   └─> github_pr_service.get_last_merged_pr()
       └─> Récupère dernière PR fusionnée = "https://github.com/owner/repo/pull/456"
   └─> db_persistence.update_last_merged_pr_url()
       └─> Sauvegarde last_merged_pr_url = "https://github.com/owner/repo/pull/456"
   
6. Fin du workflow
   └─> Base de données contient les 2 URLs
```

---

## 📝 Notes importantes

1. **pull_request_url** est sauvegardée lors de la création de la PR (nœud `finalize_pr`)
2. **last_merged_pr_url** est sauvegardée lors de la mise à jour Monday (nœud `update_monday`)
3. Les deux colonnes sont **indépendantes** et peuvent contenir des URLs différentes
4. Les deux colonnes sont **optionnelles** (peuvent être NULL)
5. La sauvegarde est **robuste** : en cas d'erreur, le workflow continue

---

## 🎯 Date de mise en œuvre

**Date** : 7 octobre 2025  
**Version** : 1.0  
**Statut** : ✅ PRODUCTION READY

---

## 📞 Vérification finale

Toutes les étapes ont été complétées avec succès :

✅ **Étape 1** : Fonction de sauvegarde créée  
✅ **Étape 2** : Aucune erreur de lint  
✅ **Étape 3** : Migration SQL appliquée  
✅ **Étape 4** : Colonne vérifiée en base  
✅ **Étape 5** : Fonction accessible  
✅ **Étape 6** : Test d'intégration créé  
✅ **Étape 7** : Test passant avec succès

**Résultat final** : Le système stocke maintenant les deux URLs de PR en base de données de manière fiable et automatique.

