# 🔄 Guide : Changement de Compte Monday.com

**Date:** 11 octobre 2025  
**Situation:** Changement du compte rranaivo13@gmail.com vers le nouveau compte Monday.com

---

## 📋 Problème Identifié

Vous avez changé de compte Monday.com et voulez utiliser le board :
- **URL**: https://rehareharanaivos-team-company.monday.com/boards/5037922237
- **Board ID**: 5037922237

Le token API actuel est associé à l'ancien compte (rranaivo13@gmail.com) et ne peut pas accéder à ce board.

---

## ✅ Solution : Mettre à Jour le Token API

### Étape 1 : Générer un Nouveau Token API Monday.com

1. **Connectez-vous** à votre nouveau compte Monday.com :
   - URL: https://rehareharanaivos-team-company.monday.com/

2. **Accédez aux paramètres de développeur** :
   - Cliquez sur votre avatar (en haut à droite)
   - Sélectionnez **"Developers"** ou **"Admin"**
   - Allez dans **"My Access Tokens"** ou **"Developer"** → **"My Apps"**

3. **Créez un nouveau token API** :
   - Cliquez sur **"Generate Token"** ou **"Create new token"**
   - Donnez-lui un nom (exemple: "AI-Agent Production")
   - Sélectionnez les scopes nécessaires :
     - ✅ `boards:read` - Lire les boards
     - ✅ `boards:write` - Écrire dans les boards
     - ✅ `updates:read` - Lire les updates/commentaires
     - ✅ `updates:write` - Créer des updates/commentaires
     - ✅ `webhooks:read` - Lire les webhooks
   - Cliquez sur **"Create"**

4. **Copiez le token** :
   - ⚠️ **IMPORTANT**: Copiez le token immédiatement, vous ne pourrez plus le voir après !
   - Format: `eyJhbGciOiJIUzI1NiJ9...` (commence souvent par `eyJ`)

### Étape 2 : Mettre à Jour le Fichier .env

Ouvrez votre fichier `.env` dans `/Users/rehareharanaivo/Desktop/AI-Agent/.env` et mettez à jour :

```bash
# ================================
# MONDAY.COM CONFIGURATION
# ================================

# ⚠️ NOUVEAU TOKEN API du nouveau compte
MONDAY_API_TOKEN=eyJhbGciOiJIUzI1NiJ9.votre-nouveau-token-ici

# Board ID du nouveau compte
MONDAY_BOARD_ID=5037922237

# Les colonnes seront vérifiées automatiquement après
MONDAY_STATUS_COLUMN_ID=status
MONDAY_REPOSITORY_URL_COLUMN_ID=link_mkwg662v

# Si vous avez aussi changé ces informations OAuth
MONDAY_CLIENT_ID=votre-nouveau-client-id
MONDAY_CLIENT_KEY=votre-nouveau-client-key
MONDAY_APP_ID=votre-nouveau-app-id
```

### Étape 3 : Vérifier la Configuration

Après avoir mis à jour le `.env`, lancez ce script pour vérifier :

```bash
cd /Users/rehareharanaivo/Desktop/AI-Agent
python3 scripts/update_to_new_board.py 5037922237
```

Ce script va :
- ✅ Vérifier que le token a accès au board
- ✅ Afficher les colonnes disponibles
- ✅ Générer la configuration correcte

### Étape 4 : Diagnostic Complet

Lancez le diagnostic complet :

```bash
python3 scripts/fix_monday_config.py
```

Vous devriez voir :
```
✅ Token valide - Connecté en tant que: [votre email]
✅ Board trouvé: [nom de votre board]
✅ Colonne status correctement configurée
✅ Colonne repository_url correctement configurée
```

### Étape 5 : Redémarrer Celery

Une fois tout configuré, redémarrez Celery pour appliquer les changements :

```bash
# Arrêter Celery (Ctrl+C dans le terminal où il tourne)

# Redémarrer Celery
celery -A services.celery_app worker --loglevel=info
```

---

## 🔍 Vérification du Board ID

Si vous n'êtes pas sûr du Board ID, vous pouvez le trouver dans l'URL :

```
https://rehareharanaivos-team-company.monday.com/boards/5037922237
                                                          ^^^^^^^^^^
                                                          Board ID
```

Ou utilisez ce script pour lister tous vos boards accessibles :

```bash
python3 scripts/list_monday_boards.py
```

---

## 🆘 Problèmes Courants

### ❌ "Board non trouvé"
**Cause**: Le token API n'a pas accès au board  
**Solution**: 
- Vérifiez que le token est bien du nouveau compte
- Vérifiez les permissions du token (scopes)
- Vérifiez que le board existe et n'est pas archivé

### ❌ "Token invalide"
**Cause**: Token mal copié ou expiré  
**Solution**: 
- Régénérez un nouveau token
- Vérifiez qu'il n'y a pas d'espaces au début/fin
- Vérifiez qu'il est bien dans le .env

### ❌ "Item non trouvé" dans les logs Celery
**Cause**: Ancienne tâche référençant l'ancien board  
**Solution**: 
```bash
python3 scripts/cleanup_old_board_tasks.py --delete --yes
```

---

## 📊 Résumé de la Configuration

### Avant (Ancien Compte)
```
Email: rranaivo13@gmail.com
Board: 2135637353 (New Board AI Agent real)
Token: ancien token
```

### Après (Nouveau Compte)
```
Email: [votre nouveau email]
Board: 5037922237 (votre nouveau board)
Token: nouveau token à configurer
```

---

## ✅ Checklist de Migration

- [ ] Token API généré depuis le nouveau compte Monday.com
- [ ] Fichier `.env` mis à jour avec le nouveau token
- [ ] Board ID mis à jour : `MONDAY_BOARD_ID=5037922237`
- [ ] Configuration vérifiée avec `python3 scripts/update_to_new_board.py 5037922237`
- [ ] Diagnostic complet OK avec `python3 scripts/fix_monday_config.py`
- [ ] Anciennes tâches nettoyées (si nécessaire)
- [ ] Celery redémarré
- [ ] Test avec une nouvelle tâche Monday.com

---

## 📞 Prochaines Étapes

1. **Générez le nouveau token API** (étape 1 ci-dessus)
2. **Mettez à jour le .env** avec ce token
3. **Lancez le script de vérification** pour valider
4. **Redémarrez Celery** pour appliquer les changements
5. **Testez** avec une nouvelle tâche dans Monday.com

---

**Besoin d'aide ?** Envoyez-moi le résultat de `python3 scripts/fix_monday_config.py` après avoir mis à jour le token.

