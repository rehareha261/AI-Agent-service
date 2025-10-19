# ✅ Corrections - Lecture de la Colonne Repository URL

## Date: 7 octobre 2025

---

## 🎯 Problème Identifié

Le système ne lisait pas correctement la colonne "Repository URL" (ID: `link_mkwg662v`) de Monday.com lors de la création de tâches depuis un webhook.

### Erreur dans les logs

```
❌ ERREUR CRITIQUE: Aucune URL GitHub trouvée dans la description ni dans les colonnes Monday.com
⚠️ Aucune colonne attendue trouvée. Colonnes disponibles: ['person', 'status', 'date4', 'link_mkwg662v']
```

### Cause Racine

Le code cherchait une colonne nommée "repo_url" ou avec des mots-clés génériques ("repo", "repository", "url", etc.) mais n'utilisait pas l'ID de colonne configuré dans `.env` (`MONDAY_REPOSITORY_URL_COLUMN_ID=link_mkwg662v`).

---

## ✅ Corrections Appliquées

### 1. Service Webhook (`services/webhook_service.py`)

**Ligne modifiée**: ~656

**Avant**:
```python
repository_url = self._extract_column_value(item_data, "repo_url", "text") or ""
```

**Après**:
```python
# ✅ CORRECTION: Lire la colonne Repository URL configurée
from config.settings import get_settings
settings = get_settings()
repository_url = ""

# Essayer d'abord avec l'ID de colonne configuré
if settings.monday_repository_url_column_id:
    # Pour une colonne de type "link", essayer "url" et "text"
    repository_url = (
        self._extract_column_value(item_data, settings.monday_repository_url_column_id, "url") or
        self._extract_column_value(item_data, settings.monday_repository_url_column_id, "text") or
        ""
    )
    if repository_url:
        logger.info(f"🔗 URL repository trouvée dans colonne configurée ({settings.monday_repository_url_column_id}): {repository_url}")

# Fallback: essayer avec le nom générique
if not repository_url:
    repository_url = self._extract_column_value(item_data, "repo_url", "text") or ""
    if repository_url:
        logger.info(f"🔗 URL repository trouvée dans colonne 'repo_url': {repository_url}")
```

### 2. Service Persistence (`services/database_persistence_service.py`)

**Lignes modifiées**: ~88-96

**Avant**:
```python
for col_id, col_value in normalized_columns.items():
    col_id_lower = col_id.lower()
    
    # URL Repository - essayer plusieurs variantes
    elif any(keyword in col_id_lower for keyword in
            ["repo", "repository", "url", "github", "git", "project"]):
        extracted_url = safe_extract_text(col_id)
        if extracted_url and ("github.com" in extracted_url or "git" in extracted_url):
            repository_url = extracted_url
            logger.info(f"🔗 URL repository trouvée dans colonne '{col_id}': {repository_url}")
```

**Après**:
```python
# ✅ NOUVEAU: Vérifier d'abord la colonne Repository URL configurée
from config.settings import get_settings
settings = get_settings()

if settings.monday_repository_url_column_id:
    extracted_url = safe_extract_text(settings.monday_repository_url_column_id)
    if extracted_url:
        repository_url = extracted_url
        logger.info(f"🔗 URL repository trouvée dans colonne configurée ({settings.monday_repository_url_column_id}): {repository_url}")

for col_id, col_value in normalized_columns.items():
    col_id_lower = col_id.lower()
    
    # URL Repository - essayer plusieurs variantes (si pas encore trouvée)
    elif not repository_url and any(keyword in col_id_lower for keyword in
            ["repo", "repository", "url", "github", "git", "project"]):
        extracted_url = safe_extract_text(col_id)
        if extracted_url and ("github.com" in extracted_url or "git" in extracted_url):
            repository_url = extracted_url
            logger.info(f"🔗 URL repository trouvée dans colonne '{col_id}': {repository_url}")
```

### 3. Amélioration Extraction Colonnes de Type "Link"

**Ligne modifiée**: ~76-99 (`database_persistence_service.py`)

**Avant**:
```python
def safe_extract_text(col_id: str, default: str = "") -> str:
    """Extrait le texte d'une colonne de manière sécurisée."""
    col_data = normalized_columns.get(col_id, {})
    if isinstance(col_data, dict):
        return (col_data.get("text") or
               col_data.get("value") or
               str(col_data.get("display_value", "")) or
               default).strip()
    return default
```

**Après**:
```python
def safe_extract_text(col_id: str, default: str = "") -> str:
    """Extrait le texte d'une colonne de manière sécurisée."""
    col_data = normalized_columns.get(col_id, {})
    if isinstance(col_data, dict):
        # Pour les colonnes de type "link", essayer url et text
        col_type = col_data.get("type", "")
        if col_type == "link":
            # Essayer d'abord la propriété "url"
            url_value = col_data.get("url")
            if url_value:
                return url_value.strip()
            # Sinon essayer "text"
            text_value = col_data.get("text")
            if text_value:
                return text_value.strip()
        
        # Essayer plusieurs propriétés possibles
        return (col_data.get("text") or
               col_data.get("value") or
               col_data.get("url") or
               str(col_data.get("display_value", "")) or
               default).strip()
    return default
```

---

## 🔍 Logique de Lecture

Le système lit maintenant la colonne Repository URL dans l'ordre suivant :

### Priorité 1: Colonne Configurée
- Utilise `MONDAY_REPOSITORY_URL_COLUMN_ID` du fichier `.env`
- Essaie d'abord la propriété `url` (pour les colonnes de type "link")
- Essaie ensuite la propriété `text`
- ✅ **C'est la méthode principale et recommandée**

### Priorité 2: Recherche par Mots-Clés
- Cherche des colonnes contenant "repo", "repository", "url", "github", "git", "project"
- Ne s'exécute que si la Priorité 1 n'a pas trouvé d'URL
- ⚠️ **Fallback uniquement**

### Priorité 3: Extraction depuis Description
- Extrait l'URL GitHub depuis la description de la tâche
- Ne s'exécute que si Priorité 1 et 2 n'ont pas trouvé d'URL
- ⚠️ **Fallback de dernier recours**

---

## 📊 Format de Données Monday.com

### Colonne de type "Link"

Monday.com renvoie les colonnes de type "link" dans ce format :

```json
{
  "id": "link_mkwg662v",
  "type": "link",
  "title": "Repository URL",
  "url": "https://github.com/user/repo",
  "text": "https://github.com/user/repo"
}
```

Le code vérifie maintenant les deux propriétés :
- `url` : Propriété principale pour les liens
- `text` : Propriété alternative

---

## ✅ Tests de Validation

### Test 1: Vérification des Lints
```bash
ruff check services/webhook_service.py services/database_persistence_service.py
```
**Résultat**: ✅ Aucune erreur

### Test 2: Vérification de la Configuration
```bash
grep MONDAY_REPOSITORY_URL_COLUMN_ID .env
```
**Résultat**: `MONDAY_REPOSITORY_URL_COLUMN_ID=link_mkwg662v`

### Test 3: Prochaine Tâche Monday.com

Au prochain webhook Monday.com, le système devrait :

1. ✅ Lire la colonne `link_mkwg662v`
2. ✅ Extraire l'URL du repository
3. ✅ Créer la tâche avec le repository_url
4. ✅ Lancer le workflow sans erreur

---

## 📝 Logs Attendus

Après correction, les logs devraient afficher :

```
🔗 URL repository trouvée dans colonne configurée (link_mkwg662v): https://github.com/user/repo
✅ Tâche créée: [titre] - [URL du repository]
🚀 Lancement du workflow...
```

Au lieu de :

```
❌ ERREUR CRITIQUE: Aucune URL GitHub trouvée dans la description ni dans les colonnes Monday.com
```

---

## 🎯 Impact

### Avant
- ❌ Le système ne trouvait pas l'URL dans la colonne Repository URL
- ❌ Obligeait l'utilisateur à mettre l'URL dans la description
- ❌ Causait l'échec de la création de tâche

### Après
- ✅ Le système lit directement la colonne Repository URL configurée
- ✅ L'utilisateur peut simplement remplir la colonne dans Monday.com
- ✅ La création de tâche fonctionne automatiquement
- ✅ Fallback sur description si la colonne est vide

---

## 🔧 Configuration Requise

Pour que les corrections fonctionnent, assurez-vous que :

1. ✅ `.env` contient : `MONDAY_REPOSITORY_URL_COLUMN_ID=link_mkwg662v`
2. ✅ La colonne "Repository URL" existe dans Monday.com
3. ✅ La colonne est de type "link" ou "text"
4. ✅ La colonne contient l'URL du repository GitHub

---

## 📋 Checklist Post-Correction

- [x] `webhook_service.py` modifié
- [x] `database_persistence_service.py` modifié
- [x] Fonction `safe_extract_text` améliorée
- [x] Support colonnes de type "link" ajouté
- [x] Priorité à la colonne configurée
- [x] Fallback sur mots-clés maintenu
- [x] Aucune erreur de lint
- [x] Logging amélioré

---

## 🚀 Prochaines Étapes

1. **Redémarrer Celery** pour appliquer les modifications
   ```bash
   # Arrêter le worker actuel (Ctrl+C)
   # Relancer avec :
   celery -A services.celery_app worker --loglevel=info
   ```

2. **Tester avec une nouvelle tâche Monday.com**
   - Créer une nouvelle tâche dans Monday.com
   - Remplir la colonne "Repository URL" avec une URL GitHub valide
   - Vérifier que le workflow se lance correctement

3. **Surveiller les logs**
   - Vérifier que le message `🔗 URL repository trouvée dans colonne configurée` apparaît
   - Confirmer que la tâche se crée sans erreur
   - Valider que le workflow démarre

---

**Date**: 7 octobre 2025  
**Version**: 1.0  
**Statut**: ✅ CORRECTIONS APPLIQUÉES - REDÉMARRAGE CELERY REQUIS

