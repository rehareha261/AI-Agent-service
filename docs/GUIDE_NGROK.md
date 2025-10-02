# 🌐 Guide d'utilisation de ngrok avec l'Agent IA

## 🎯 Pourquoi ngrok est nécessaire ?

Ce projet utilise des **webhooks Monday.com** qui doivent pouvoir atteindre votre application locale. Monday.com ne peut pas envoyer des webhooks vers `localhost:8000`, il faut une URL publique.

## 📥 Installation de ngrok

### Option 1: Installation directe
```bash
# macOS avec Homebrew
brew install ngrok/ngrok/ngrok

# Ou télécharger depuis https://ngrok.com/download
```

### Option 2: npm
```bash
npm install -g ngrok
```

## 🔑 Configuration initiale

```bash
# S'inscrire sur ngrok.com et récupérer votre token
ngrok config add-authtoken VOTRE_TOKEN_NGROK
```

## 🚀 Utilisation avec le projet

### 1. Démarrer votre application
```bash
# Terminal 1 - Démarrer l'agent IA
cd /Users/stagiaire_vycode/Stage/AI-Agent
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Démarrer ngrok
```bash
# Terminal 2 - Exposer le port 8000
ngrok http 8000
```

**Résultat ngrok :**
```
ngrok                                                          

Session Status                online
Account                      votre@email.com
Version                      3.x.x
Region                       Europe (eu)
Latency                      45ms
Web Interface                http://127.0.0.1:4040
Forwarding                   https://abcd-1234-efgh-5678.ngrok.io -> http://localhost:8000

Connections                  ttl     opn     rt1     rt5     p50     p90
                            0       0       0.00    0.00    0.00    0.00
```

### 3. Configuration Monday.com

1. **Copier l'URL ngrok** : `https://abcd-1234-efgh-5678.ngrok.io`

2. **Configurer le webhook Monday.com :**
   - Aller dans votre board Monday.com
   - Paramètres → Intégrations → Webhooks
   - **URL webhook** : `https://abcd-1234-efgh-5678.ngrok.io/webhook/monday`
   - **Événements** : "Item created", "Item updated"
   - **Secret** : Votre `WEBHOOK_SECRET` du fichier .env

### 4. Test de la configuration

```bash
# Tester l'endpoint de santé via ngrok
curl https://abcd-1234-efgh-5678.ngrok.io/health

# Devrait retourner:
# {"status":"healthy","service":"ai-automation-agent","version":"1.0.0"}
```

## 🔧 Workflow complet de développement

### Session de travail type :

```bash
# Terminal 1 - Application
cd /Users/stagiaire_vycode/Stage/AI-Agent
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 - ngrok
ngrok http 8000

# Terminal 3 - Tests/monitoring
curl https://VOTRE-URL-NGROK.ngrok.io/health
tail -f logs/app.log  # Si vous avez des logs
```

## 📊 Monitoring ngrok

### Interface web ngrok
- Ouvrir : http://127.0.0.1:4040
- Voir toutes les requêtes en temps réel
- Débugger les webhooks Monday.com

### Logs utiles
```bash
# Voir les requêtes ngrok en temps réel
# (dans l'interface web ngrok)

# Logs de votre application
# (dans le terminal où tourne uvicorn)
```

## 🚨 Points d'attention

### 1. URL ngrok change à chaque redémarrage
```bash
# ATTENTION: L'URL change quand vous redémarrez ngrok !
# Ancienne URL: https://abcd-1234.ngrok.io
# Nouvelle URL: https://wxyz-9876.ngrok.io

# Il faut mettre à jour Monday.com à chaque fois
```

### 2. Solution pour URL fixe (Payant)
```bash
# Avec un compte ngrok payant, vous pouvez avoir une URL fixe:
ngrok http 8000 --subdomain=mon-agent-ia
# URL fixe: https://mon-agent-ia.ngrok.io
```

### 3. Alternative avec un domaine personnel
```bash
# Si vous avez un domaine, utilisez ngrok avec:
ngrok http 8000 --hostname=webhook.mondomaine.com
```

## 🐛 Debug des webhooks

### Vérifier que Monday.com peut atteindre votre webhook

```bash
# 1. Créer une tâche dans Monday.com
# 2. Vérifier les logs ngrok (interface web)
# 3. Vérifier les logs de votre application

# Test manuel du webhook
curl -X POST https://VOTRE-URL-NGROK.ngrok.io/webhook/monday \
  -H "Content-Type: application/json" \
  -d '{"challenge": "test"}'
```

### Common issues

```bash
# Problème 1: ngrok non accessible
# Solution: Vérifier que ngrok est bien démarré

# Problème 2: Webhook Monday.com ne fonctionne pas
# Solution: Vérifier l'URL dans la configuration Monday.com

# Problème 3: Erreur CORS
# Solution: Vérifier ALLOWED_ORIGINS dans .env
```

## 📝 Checklist de mise en route

- [ ] ngrok installé et configuré avec authtoken
- [ ] Application qui tourne sur port 8000
- [ ] ngrok qui expose le port 8000
- [ ] URL ngrok configurée dans Monday.com webhook
- [ ] Test de l'endpoint /health réussi
- [ ] Test de création d'une tâche Monday.com

## 🚀 Production

Pour la production, remplacez ngrok par :
- Un serveur avec IP publique
- Un service cloud (Heroku, Railway, etc.)
- Un reverse proxy (Cloudflare Tunnel, etc.)

---

**Note importante** : ngrok est parfait pour le développement mais pas recommandé pour la production à cause de l'URL qui change. 