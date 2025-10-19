# Automatisation de la Colonne Repository URL

## Vue d'ensemble

Cette fonctionnalité automatise la mise à jour de la colonne **Repository URL** dans Monday.com avec l'URL de la dernière Pull Request fusionnée sur GitHub. Cela permet de toujours avoir un lien direct vers les dernières modifications dans votre repository.

## Fonctionnement

### Workflow

1. **Lecture de l'URL du repository** : Au début du workflow, l'agent lit l'URL du repository depuis :
   - La colonne `Repository URL` de Monday.com (priorité haute)
   - La description de la tâche (fallback)
   - Les updates de Monday.com (dernier fallback)

2. **Exécution du workflow** : L'agent exécute toutes les étapes du workflow (analyse, implémentation, tests, etc.)

3. **Mise à jour automatique** : À la fin du workflow, dans le nœud `update_monday` :
   - L'agent récupère la dernière PR fusionnée sur le repository GitHub
   - Met à jour la colonne `Repository URL` avec l'URL de cette PR
   - Si aucune PR fusionnée n'est trouvée, utilise l'URL du repository de base

### Schéma du flux

```
Début du Workflow
    ↓
Lecture Repository URL (Monday.com → Description → Updates)
    ↓
Exécution du Workflow (prepare → analyze → implement → test → ...)
    ↓
Fin du Workflow (update_monday)
    ↓
Récupération dernière PR fusionnée (GitHub API)
    ↓
Mise à jour colonne Repository URL (Monday.com)
    ↓
Fin
```

## Configuration

### Étape 1: Créer la colonne dans Monday.com

1. Ouvrez votre board Monday.com
2. Cliquez sur le bouton **+** pour ajouter une nouvelle colonne
3. Sélectionnez le type **Texte** ou **Lien**
4. Nommez la colonne **"Repository URL"**

### Étape 2: Configurer l'ID de la colonne

Exécutez le script de configuration automatique :

```bash
python scripts/ensure_repository_url_column.py
```

Ce script va :
- Vérifier si la colonne existe
- Récupérer son ID
- Mettre à jour automatiquement votre fichier `.env`

Ou manuellement, ajoutez dans votre `.env` :

```env
MONDAY_REPOSITORY_URL_COLUMN_ID=votre_column_id_ici
```

### Étape 3: Vérifier la configuration

Vérifiez que le champ est bien configuré dans votre `.env` :

```bash
grep MONDAY_REPOSITORY_URL_COLUMN_ID .env
```

## Tests

### Test complet de l'intégration

Exécutez le script de test :

```bash
python tests/test_repository_url_update.py
```

Ce script teste :
1. ✅ Le service de récupération de la dernière PR fusionnée
2. ✅ L'existence de la colonne Repository URL dans Monday.com
3. ✅ La simulation de mise à jour de la colonne

### Test manuel dans un workflow

1. Créez une tâche dans Monday.com avec une URL de repository dans la colonne `Repository URL`
2. Déclenchez un workflow via Monday.com
3. Attendez la fin du workflow
4. Vérifiez que la colonne `Repository URL` a été mise à jour avec l'URL de la dernière PR fusionnée

## Structure du Code

### Nouveaux fichiers

- **`services/github_pr_service.py`** : Service pour récupérer les informations des PRs GitHub
- **`scripts/ensure_repository_url_column.py`** : Script de configuration de la colonne Monday.com
- **`tests/test_repository_url_update.py`** : Tests d'intégration

### Fichiers modifiés

- **`config/settings.py`** : Ajout du champ `monday_repository_url_column_id`
- **`nodes/update_node.py`** : Ajout de la fonction `_update_repository_url_column()`
- **`nodes/prepare_node.py`** : Lecture de l'URL depuis la colonne Repository URL (déjà présent)

## API GitHub utilisée

Le service utilise l'API GitHub pour récupérer les Pull Requests :

```python
# Récupérer la dernière PR fusionnée
result = await github_pr_service.get_last_merged_pr(repo_url)

# Structure de la réponse
{
    "success": True,
    "pr_number": 123,
    "pr_title": "Fix bug in authentication",
    "pr_url": "https://github.com/owner/repo/pull/123",
    "merged_at": "2025-10-07T12:34:56Z",
    "merged_by": "username",
    "head_branch": "feature/fix-auth",
    "base_branch": "main",
    "commit_sha": "abc123..."
}
```

## Dépannage

### La colonne n'est pas mise à jour

1. **Vérifiez la configuration** :
   ```bash
   python scripts/ensure_repository_url_column.py
   ```

2. **Vérifiez les logs** :
   ```bash
   tail -f logs/workflows.log | grep "Repository URL"
   ```

3. **Vérifiez le token GitHub** :
   - Assurez-vous que `GITHUB_TOKEN` a les permissions de lecture des PRs

### Erreur "Colonne Repository URL non configurée"

Ajoutez la variable d'environnement :

```env
MONDAY_REPOSITORY_URL_COLUMN_ID=votre_column_id_ici
```

### Erreur "Aucune PR fusionnée trouvée"

C'est normal si :
- Le repository n'a pas encore de PR fusionnée
- Dans ce cas, l'URL du repository de base est utilisée

## Avantages

✅ **Traçabilité** : Lien direct vers la dernière modification
✅ **Automatisation** : Plus besoin de mettre à jour manuellement
✅ **Contexte** : Accès rapide aux changements récents
✅ **Historique** : Monday.com garde l'historique des modifications

## Exemple d'utilisation

### Avant

```
Monday.com → Update Section → "Repo: https://github.com/user/repo"
```

### Après

```
Monday.com → Repository URL Column → "https://github.com/user/repo/pull/42"
                                      (Mise à jour automatiquement après chaque workflow)
```

## Questions Fréquentes

**Q: Que se passe-t-il si aucune PR n'est fusionnée ?**  
R: L'agent utilise l'URL du repository de base dans ce cas.

**Q: La colonne est-elle mise à jour à chaque workflow ?**  
R: Oui, à la fin de chaque workflow réussi.

**Q: Puis-je désactiver cette fonctionnalité ?**  
R: Oui, retirez simplement `MONDAY_REPOSITORY_URL_COLUMN_ID` de votre `.env`.

**Q: Cela fonctionne-t-il avec des repositories privés ?**  
R: Oui, tant que votre `GITHUB_TOKEN` a les permissions nécessaires.

## Support

Pour toute question ou problème :
1. Consultez les logs : `logs/workflows.log`
2. Exécutez les tests : `python tests/test_repository_url_update.py`
3. Vérifiez la configuration : `python scripts/ensure_repository_url_column.py`

