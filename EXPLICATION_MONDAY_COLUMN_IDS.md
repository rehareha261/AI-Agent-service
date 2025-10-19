# 📚 Explication : IDs de Colonnes Monday.com

## Date: 7 octobre 2025

---

## ❓ Question Initiale

**"Pourquoi utiliser `link_mkwg662v` au lieu de `Repository URL` ?"**

---

## ✅ Réponse : Ce n'est PAS une erreur !

### C'est le fonctionnement normal de l'API Monday.com

Monday.com utilise **deux identifiants différents** pour chaque colonne :

| Type | Valeur | Usage | Modifiable ? |
|------|--------|-------|--------------|
| **Titre** | `Repository URL` | Interface utilisateur | ✅ Oui, vous pouvez renommer |
| **ID** | `link_mkwg662v` | API / Code | ❌ Non, permanent |

---

## 🔍 Vérification dans Votre Board

Voici le mapping actuel de votre colonne :

```
┌──────────────────────────────────────────────────┐
│  MONDAY.COM INTERFACE (ce que vous voyez)        │
│                                                  │
│  Colonne: "Repository URL"                       │
│  Type: Link                                      │
│                                                  │
└──────────────────────────────────────────────────┘
                     ↕
                  (mapping)
                     ↕
┌──────────────────────────────────────────────────┐
│  API MONDAY.COM (ce que le code utilise)         │
│                                                  │
│  Column ID: "link_mkwg662v"                      │
│  Column Type: "link"                             │
│                                                  │
└──────────────────────────────────────────────────┘
```

**✅ Vérification effectuée** : Le mapping est **CORRECT**

---

## 📖 Pourquoi Monday.com utilise des IDs ?

### Raison 1: Stabilité

Si vous renommez la colonne de `Repository URL` à `GitHub URL`, le code continue de fonctionner car il utilise l'ID permanent `link_mkwg662v`.

**Exemple** :
```
Jour 1:  Titre = "Repository URL"    → ID = "link_mkwg662v"
Jour 2:  Titre = "GitHub URL"        → ID = "link_mkwg662v" (inchangé)
Jour 3:  Titre = "Repo"              → ID = "link_mkwg662v" (inchangé)
```

Le code fonctionne dans tous les cas ! ✅

### Raison 2: Unicité

Deux colonnes peuvent avoir le même titre, mais jamais le même ID.

**Exemple** :
```
Board Marketing:
  - Colonne "Status"    → ID: "status_abc123"
  
Board Développement:
  - Colonne "Status"    → ID: "status_xyz789"
```

### Raison 3: Internationalisation

Le titre peut être en français, anglais, etc. L'ID reste le même.

**Exemple** :
```
Français:  Titre = "URL du Repository"  → ID = "link_mkwg662v"
English:   Titre = "Repository URL"     → ID = "link_mkwg662v"
```

---

## 🔧 Comment Monday.com génère les IDs

Monday.com génère automatiquement des IDs uniques lors de la création d'une colonne :

### Format des IDs

```
[type]_[random_string]
```

**Exemples dans votre board** :
- `link_mkwg662v` → Colonne de type "link"
- `status` → Colonne de type "status" (nom simplifié)
- `person` → Colonne de type "person" (nom simplifié)
- `date4` → Colonne de type "date" (avec suffixe numérique)

---

## 💻 Comment le Code Utilise les IDs

### Dans votre fichier `.env`

```env
MONDAY_REPOSITORY_URL_COLUMN_ID=link_mkwg662v
```

☝️ C'est l'**ID API**, pas le titre !

### Dans le code Python

```python
# ✅ CORRECT : Utiliser l'ID
settings.monday_repository_url_column_id  # → "link_mkwg662v"
repository_url = self._extract_column_value(
    item_data, 
    "link_mkwg662v",  # ← ID de la colonne
    "url"
)

# ❌ INCORRECT : Utiliser le titre
repository_url = self._extract_column_value(
    item_data, 
    "Repository URL",  # ← NE MARCHE PAS !
    "url"
)
```

### Requête GraphQL à Monday.com

```graphql
query {
  items(ids: 5031747032) {
    column_values {
      id        # → "link_mkwg662v" (ce qu'on reçoit)
      title     # → "Repository URL" (pour référence)
      text      # → "https://github.com/..."
      value     # → JSON complet
    }
  }
}
```

Monday.com **renvoie toujours les IDs**, jamais les titres !

---

## 📊 Toutes les Colonnes de Votre Board

Voici le mapping complet (visible vs API) :

| Titre Visible | ID API | Type |
|---------------|--------|------|
| Person | `person` | Person |
| Status | `status` | Status |
| Date | `date4` | Date |
| **Repository URL** | **`link_mkwg662v`** | **Link** |

---

## 🎯 Pourquoi C'est Important

### Scénario sans IDs (système fragile ❌)

```python
# Si on utilisait les titres...
if column_title == "Repository URL":
    url = get_value()

# Problème 1: Si vous renommez la colonne → CODE CASSÉ
# Problème 2: Si vous traduisez → CODE CASSÉ
# Problème 3: Si vous avez une typo → CODE CASSÉ
```

### Scénario avec IDs (système robuste ✅)

```python
# Avec les IDs...
if column_id == "link_mkwg662v":
    url = get_value()

# ✅ Fonctionne même si vous renommez
# ✅ Fonctionne en toutes langues
# ✅ Pas de problème de typo
```

---

## 🛠️ Comment Trouver l'ID d'une Colonne

### Méthode 1: Utiliser notre script

```bash
python3 scripts/ensure_repository_url_column.py
```

Le script affiche :
```
✅ Colonne trouvée: 'Repository URL' (ID: link_mkwg662v, Type: link)
```

### Méthode 2: API Monday.com

```bash
curl -X POST https://api.monday.com/v2 \
  -H "Authorization: YOUR_TOKEN" \
  -d '{
    "query": "{ boards(ids: 2135637353) { columns { id title type } } }"
  }'
```

### Méthode 3: Inspector du navigateur

1. Ouvrez Monday.com
2. Clic droit sur la colonne → "Inspecter"
3. Cherchez `data-column-id` dans le HTML

---

## 📝 Exemples Concrets

### Exemple 1: Lire la colonne Repository URL

```python
from config.settings import get_settings

settings = get_settings()

# ✅ CORRECT
column_id = settings.monday_repository_url_column_id  # "link_mkwg662v"
url = extract_value(item_data, column_id)

# ❌ INCORRECT
url = extract_value(item_data, "Repository URL")
```

### Exemple 2: Mettre à jour la colonne

```python
# ✅ CORRECT
await monday_tool._arun(
    action="update_column_value",
    item_id=5031747032,
    column_id="link_mkwg662v",  # ← ID
    value="https://github.com/user/repo"
)

# ❌ INCORRECT
await monday_tool._arun(
    action="update_column_value",
    item_id=5031747032,
    column_id="Repository URL",  # ← Titre (ne marche pas)
    value="https://github.com/user/repo"
)
```

---

## ✅ Conclusion

### Ce que vous devez retenir :

1. **`Repository URL`** = Titre visible dans Monday.com
   - ✅ Vous pouvez le modifier quand vous voulez
   - ❌ Ne doit PAS être utilisé dans le code

2. **`link_mkwg662v`** = ID permanent pour l'API
   - ✅ Doit être utilisé dans le code
   - ❌ Ne change JAMAIS

3. **Le système actuel est CORRECT** ✅
   - Configuration : `MONDAY_REPOSITORY_URL_COLUMN_ID=link_mkwg662v`
   - Le code lit la bonne colonne
   - Aucune correction nécessaire

---

## 🚀 Actions Suivantes

Maintenant que vous comprenez le système :

1. ✅ **Aucune modification nécessaire** - Le code est correct
2. ✅ **Redémarrer Celery** pour appliquer les corrections précédentes
3. ✅ **Tester** avec une nouvelle tâche Monday.com

---

**Date de création** : 7 octobre 2025  
**Statut** : ✅ Système validé - Aucune erreur d'encodage - Fonctionnement normal de Monday.com

