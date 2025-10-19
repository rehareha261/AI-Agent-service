# 🔧 Guide de Résolution : Erreur GitHub 403 - Permission Denied

## ❌ Symptôme

```
❌ Erreur de permissions GitHub (403):
remote: Permission to rehareha261/rehareha261.git denied to rehareha261.
fatal: unable to access 'https://github.com/rehareha261/rehareha261/': The requested URL returned error: 403
```

## 🔍 Cause

Votre token GitHub (`GITHUB_TOKEN`) n'a **pas les permissions suffisantes** pour pousser du code.

## ✅ Solution : Créer un nouveau token avec les bonnes permissions

### Étape 1 : Générer un nouveau Personal Access Token

1. **Allez sur GitHub** : https://github.com/settings/tokens

2. **Cliquez sur** `Personal access tokens` → `Tokens (classic)`

3. **Cliquez sur** `Generate new token` → `Generate new token (classic)`

4. **Configurez le token** :
   - **Note** : `AI-Agent Token - Full Access`
   - **Expiration** : `90 days` (ou `No expiration` si vous préférez)

5. **Cochez TOUTES ces permissions** :
   ```
   ✅ repo                          (Accès complet aux repositories)
      ✅ repo:status                (Accès au statut des commits)
      ✅ repo_deployment            (Accès aux déploiements)
      ✅ public_repo                (Accès aux repos publics)
      ✅ repo:invite                (Accès aux invitations)
      ✅ security_events            (Lecture/écriture des événements de sécurité)
   
   ✅ workflow                      (Mise à jour des workflows GitHub Actions)
   
   ✅ write:packages                (Upload de packages)
   ✅ read:packages                 (Téléchargement de packages)
   
   ✅ delete_repo                   (Suppression de repositories - optionnel)
   ```

6. **Cliquez sur** `Generate token`

7. **COPIEZ LE TOKEN IMMÉDIATEMENT** (vous ne pourrez plus le voir après)
   ```
   ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

---

### Étape 2 : Mettre à jour votre fichier `.env`

1. **Ouvrez votre fichier `.env`** à la racine du projet :
   ```bash
   cd /Users/rehareharanaivo/Desktop/AI-Agent
   nano .env
   ```

2. **Remplacez l'ancien token** :
   ```bash
   # Ancien (à remplacer)
   GITHUB_TOKEN=ghp_ancien_token_invalide
   
   # Nouveau (avec les bonnes permissions)
   GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

3. **Sauvegardez** : `Ctrl+O` puis `Enter`, puis `Ctrl+X`

---

### Étape 3 : Vérifier que le token fonctionne

```bash
# Test 1 : Vérifier l'authentification
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user

# Test 2 : Vérifier l'accès au repository
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/repos/rehareha261/rehareha261

# Résultat attendu : Vous devez voir vos informations utilisateur et repository en JSON
```

---

### Étape 4 : Redémarrer les services

```bash
# 1. Arrêter Celery
pkill -f celery

# 2. Redémarrer Celery (il va recharger le nouveau token)
celery -A services.celery_app worker --loglevel=info
```

---

## 🎯 Checklist de vérification

- [ ] Token généré avec les scopes `repo` et `workflow`
- [ ] Token copié dans le `.env`
- [ ] Test curl réussi
- [ ] Celery redémarré
- [ ] Nouvelle tâche testée avec succès

---

## 🔐 Sécurité

⚠️ **IMPORTANT** :
- **NE JAMAIS** commiter le fichier `.env` dans Git
- **NE JAMAIS** partager votre token
- Le `.gitignore` doit contenir `.env`
- Régénérez le token si compromis

---

## 📋 Permissions détaillées expliquées

| Permission | Nécessaire ? | Raison |
|-----------|--------------|---------|
| `repo` | ✅ **OUI** | Permet de pousser du code, créer des branches |
| `workflow` | ✅ **OUI** | Permet de modifier les GitHub Actions workflows |
| `write:packages` | ⚠️ Optionnel | Utile si vous publiez des packages |
| `delete_repo` | ❌ Non | Seulement si vous voulez supprimer des repos |

---

## 🆘 Problèmes courants

### Erreur persiste après avoir changé le token

```bash
# 1. Vérifier que le token est bien dans .env
cat .env | grep GITHUB_TOKEN

# 2. Vérifier que Celery a bien rechargé
ps aux | grep celery

# 3. Redémarrer complètement
./stop_all.sh
celery -A services.celery_app worker --loglevel=info
```

### Token invalide même après regénération

- Vérifiez que vous avez copié le token **COMPLET**
- Vérifiez qu'il n'y a **pas d'espace** avant/après dans le `.env`
- Le token doit commencer par `ghp_` (classic) ou `github_pat_` (fine-grained)

---

## 📞 Support

Si le problème persiste :
1. Vérifiez les logs : `tail -f logs/celery.log`
2. Vérifiez que le repository existe : https://github.com/rehareha261/rehareha261
3. Vérifiez que vous avez les droits d'écriture sur ce repository

