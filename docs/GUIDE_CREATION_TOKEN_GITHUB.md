# 🔑 Guide Complet : Créer un Token GitHub avec les BONNES Permissions

## ⚠️ PROBLÈME ACTUEL
Votre token a seulement **"public access"** → **INSUFFISANT** ❌

Vous avez besoin d'un token avec **"repo"** (accès complet) → **REQUIS** ✅

---

## 📋 ÉTAPES DÉTAILLÉES

### **Étape 1 : Supprimer l'ancien token**

1. Sur la page : https://github.com/settings/tokens
2. Trouvez le token `ai agent`
3. Cliquez sur **Delete** (bouton rouge à droite)
4. Confirmez la suppression

---

### **Étape 2 : Créer un NOUVEAU token**

1. **Cliquez sur** le bouton vert `Generate new token` en haut à droite
2. **Sélectionnez** `Generate new token (classic)` dans le menu déroulant

---

### **Étape 3 : Remplir le formulaire**

#### A) **Note** (nom du token)
```
AI-Agent Full Access
```

#### B) **Expiration**
Choisissez : `90 days` (ou `No expiration` si vous voulez qu'il ne expire jamais)

#### C) **Select scopes** (PARTIE LA PLUS IMPORTANTE ⚠️)

Vous allez voir une LONGUE liste de checkboxes. Voici EXACTEMENT ce qu'il faut cocher :

---

## ✅ **PERMISSIONS À COCHER (COPIER-COLLER CETTE LISTE)**

### 🔴 **1. repo** ← LA PLUS IMPORTANTE !
```
☑️ repo                             (Accès complet aux repositories)
   ☑️ repo:status                   (Accès au statut des commits)
   ☑️ repo_deployment               (Accès aux déploiements)  
   ☑️ public_repo                   (Accès aux repos publics)
   ☑️ repo:invite                   (Accès aux invitations)
   ☑️ security_events               (Lecture/écriture des événements de sécurité)
```

**COMMENT COCHER** :
- Cliquez sur la case `☑️ repo` en haut
- Toutes les sous-cases se cocheront automatiquement ✅

---

### 🔵 **2. workflow** (Important pour les GitHub Actions)
```
☑️ workflow                         (Mise à jour des workflows GitHub Actions)
```

---

### 🟢 **3. write:packages** (Optionnel mais recommandé)
```
☑️ write:packages                   (Upload de packages vers GitHub Packages)
☑️ read:packages                    (Téléchargement de packages)
```

---

### 🟡 **4. delete_repo** (Optionnel - DANGEREUX)
```
☐ delete_repo                       (Ne PAS cocher sauf si nécessaire)
```

---

## 📸 **À QUOI ÇA DOIT RESSEMBLER**

Après avoir coché, vous devriez voir ceci :

```
Select scopes

Scopes define the access for personal tokens. Read more about OAuth scopes.

☑️ repo                Full control of private repositories
   ☑️ repo:status      Access commit status
   ☑️ repo_deployment  Access deployment status
   ☑️ public_repo      Access public repositories
   ☑️ repo:invite      Access repository invitations
   ☑️ security_events  Read and write security events

☑️ workflow            Update GitHub Action workflows

☑️ write:packages      Upload packages to GitHub Package Registry
☑️ read:packages       Download packages from GitHub Package Registry

☐ delete_repo          Delete repositories (LAISSER DÉCOCHÉ)

admin:repo_hook        Full control of repository hooks
   ☐ write:repo_hook   Write repository hooks
   ☐ read:repo_hook    Read repository hooks

... (autres options non nécessaires)
```

---

### **Étape 4 : Générer le token**

1. **Scrollez tout en bas** de la page
2. **Cliquez sur** le bouton vert `Generate token`
3. **ATTENDEZ** que la page se recharge

---

### **Étape 5 : COPIER LE TOKEN IMMÉDIATEMENT** ⚠️

Vous allez voir une page avec :

```
┌─────────────────────────────────────────────────────────────┐
│ ✅ Personal access token generated                          │
│                                                               │
│ Make sure to copy your personal access token now.           │
│ You won't be able to see it again!                          │
│                                                               │
│ ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  [Copy] 📋          │
└─────────────────────────────────────────────────────────────┘
```

**ACTIONS** :
1. ✅ Cliquez sur le bouton **[Copy]** (icône 📋)
2. ✅ Collez-le **IMMÉDIATEMENT** dans un fichier texte temporaire
3. ✅ Vous devriez avoir quelque chose comme : `ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0`

⚠️ **IMPORTANT** : Une fois que vous quittez cette page, vous ne pourrez **PLUS JAMAIS** voir ce token !

---

## 🔧 **Étape 6 : Mettre à jour le fichier .env**

### A) Ouvrir le terminal

```bash
cd /Users/rehareharanaivo/Desktop/AI-Agent
```

### B) Éditer le fichier .env

**Option 1 : Avec nano**
```bash
nano .env
```

**Option 2 : Avec VS Code**
```bash
code .env
```

### C) Remplacer la ligne GITHUB_TOKEN

**AVANT** (mauvais token) :
```bash
GITHUB_TOKEN=ghp_ancien_token_avec_public_access_seulement
```

**APRÈS** (bon token) :
```bash
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
↑ Collez votre NOUVEAU token ici (celui que vous venez de copier)

### D) Sauvegarder

**Si vous utilisez nano** :
1. Appuyez sur `Ctrl+O` (pour "Output" = sauvegarder)
2. Appuyez sur `Enter` (pour confirmer le nom du fichier)
3. Appuyez sur `Ctrl+X` (pour quitter)

**Si vous utilisez VS Code** :
1. `Cmd+S` (Mac) ou `Ctrl+S` (Windows)
2. Fermez le fichier

---

## ✅ **Étape 7 : Vérifier que le token fonctionne**

### Test 1 : Vérifier l'authentification de base

```bash
curl -H "Authorization: token $(grep GITHUB_TOKEN .env | cut -d '=' -f2)" https://api.github.com/user
```

**Résultat attendu** :
```json
{
  "login": "rehareha261",
  "id": 12345678,
  "type": "User",
  ...
}
```

✅ Si vous voyez vos infos → **Token valide** !
❌ Si vous voyez une erreur 401 → Token invalide, recommencez

---

### Test 2 : Vérifier l'accès au repository

```bash
curl -H "Authorization: token $(grep GITHUB_TOKEN .env | cut -d '=' -f2)" \
  https://api.github.com/repos/rehareha261/rehareha261
```

**Résultat attendu** :
```json
{
  "id": 87654321,
  "name": "rehareha261",
  "full_name": "rehareha261/rehareha261",
  "private": false,
  "permissions": {
    "admin": true,    ← Vous devez avoir "true" ici
    "push": true,     ← Vous devez avoir "true" ici
    "pull": true
  },
  ...
}
```

✅ Si `"push": true` → **Vous pouvez pousser du code** !
❌ Si `"push": false` → Le token n'a pas les bonnes permissions

---

### Test 3 : Vérifier les scopes du token

```bash
TOKEN=$(grep GITHUB_TOKEN .env | cut -d '=' -f2)
curl -I -H "Authorization: token $TOKEN" https://api.github.com/user 2>&1 | grep -i x-oauth-scopes
```

**Résultat attendu** :
```
x-oauth-scopes: repo, workflow, write:packages
```

✅ Vous DEVEZ voir `repo` dans la liste !

---

## 🚀 **Étape 8 : Redémarrer Celery**

Le worker Celery doit être redémarré pour charger le nouveau token.

### A) Arrêter Celery

```bash
# Trouver le processus
ps aux | grep celery

# Tuer tous les processus Celery
pkill -f celery

# Vérifier qu'ils sont bien arrêtés
ps aux | grep celery
```

### B) Redémarrer Celery

```bash
cd /Users/rehareharanaivo/Desktop/AI-Agent
celery -A services.celery_app worker --loglevel=info
```

Vous devriez voir :
```
✅ Claude provider initialisé
✅ OpenAI provider initialisé
🚀 Celery worker prêt
```

---

## 🧪 **Étape 9 : Tester avec une nouvelle tâche**

1. Allez sur Monday.com
2. Créez une nouvelle tâche (ou changez le statut d'une tâche existante)
3. Observez les logs de Celery
4. Cette fois, le push devrait réussir ! 🎉

---

## 🔍 **CHECKLIST FINALE**

Vérifiez que vous avez bien :

- [ ] ✅ Supprimé l'ancien token "ai agent"
- [ ] ✅ Créé un nouveau token
- [ ] ✅ Coché la case **"repo"** (la plus importante !)
- [ ] ✅ Coché la case **"workflow"**
- [ ] ✅ Copié le token complet (commence par `ghp_`)
- [ ] ✅ Mis à jour le fichier `.env`
- [ ] ✅ Le test curl montre `"push": true`
- [ ] ✅ Le test scopes montre `repo, workflow`
- [ ] ✅ Redémarré Celery
- [ ] ✅ Aucune erreur 403 dans les logs

---

## ❌ **ERREURS COURANTES**

### Erreur : "Bad credentials"
```json
{
  "message": "Bad credentials",
  "documentation_url": "..."
}
```

**Cause** : Token mal copié ou avec des espaces

**Solution** :
```bash
# Vérifier le token dans .env
cat .env | grep GITHUB_TOKEN

# Le token doit :
# ✅ Commencer par ghp_
# ✅ Avoir 40 caractères après ghp_
# ✅ Ne pas avoir d'espaces avant/après
# ❌ Ne pas avoir de guillemets autour
```

---

### Erreur : Toujours 403 après avoir changé le token

**Solutions** :
1. Vérifiez que Celery a bien été redémarré
2. Vérifiez que le scope `repo` est bien dans le token (test 3 ci-dessus)
3. Assurez-vous que vous êtes bien le propriétaire du repository

---

## 🆘 **Besoin d'aide ?**

Si ça ne fonctionne toujours pas après avoir suivi TOUTES ces étapes :

1. **Vérifiez les logs Celery** :
   ```bash
   tail -f logs/celery.log
   ```

2. **Vérifiez que le repository existe** :
   ```bash
   curl https://api.github.com/repos/rehareha261/rehareha261
   ```

3. **Envoyez-moi** :
   - La sortie du test 2 (permissions)
   - La sortie du test 3 (scopes)
   - Les logs de l'erreur dans Celery

---

## 🎯 **RÉCAPITULATIF VISUEL**

```
┌─────────────────────────────────────────────────────┐
│  TOKEN ACTUEL (MAUVAIS) ❌                          │
├─────────────────────────────────────────────────────┤
│  ai agent — public access                           │
│  Expires on Sat, Nov 1 2025                         │
│                                                      │
│  Permissions : Lecture seule des repos publics      │
│  Peut faire  : Rien (juste lire)                    │
└─────────────────────────────────────────────────────┘

                        ⬇️ REMPLACER PAR ⬇️

┌─────────────────────────────────────────────────────┐
│  NOUVEAU TOKEN (BON) ✅                             │
├─────────────────────────────────────────────────────┤
│  AI-Agent Full Access                               │
│  Expires on Sat, Nov 1 2025                         │
│                                                      │
│  Scopes : repo, workflow, write:packages            │
│  Peut faire :                                        │
│    ✅ Pousser du code                               │
│    ✅ Créer des branches                            │
│    ✅ Créer des Pull Requests                       │
│    ✅ Modifier des fichiers                         │
└─────────────────────────────────────────────────────┘
```

