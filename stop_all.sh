#!/bin/bash

echo "🛑 ARRÊT COMPLET DU SYSTÈME AI-AGENT"
echo "===================================="

# 1. Arrêter tous les processus Celery
echo "1️⃣ Arrêt des workers Celery..."
pkill -f "celery.*worker" 2>/dev/null || echo "Aucun worker Celery en cours"
pkill -f "celery.*beat" 2>/dev/null || echo "Aucun beat Celery en cours"

# 2. Arrêter les processus Python du projet
echo "2️⃣ Arrêt des processus Python du projet..."
pgrep -f "python.*main.py" | xargs kill -TERM 2>/dev/null || echo "Aucun processus main.py"
pgrep -f "uvicorn.*main" | xargs kill -TERM 2>/dev/null || echo "Aucun serveur uvicorn"

# 3. Reset complet de RabbitMQ
echo "3️⃣ Reset complet de RabbitMQ..."
if docker ps --format '{{.Names}}' | grep -q "ai_agent_rabbitmq"; then
    echo "   📡 Arrêt de l'application RabbitMQ..."
    docker exec ai_agent_rabbitmq rabbitmqctl stop_app
    
    echo "   🧹 Reset complet des données RabbitMQ..."
    docker exec ai_agent_rabbitmq rabbitmqctl reset
    
    echo "   🚀 Redémarrage de l'application RabbitMQ..."
    docker exec ai_agent_rabbitmq rabbitmqctl start_app
    
    echo "   ✅ RabbitMQ reset avec succès"
else
    echo "   ⚠️ Container RabbitMQ non trouvé"
fi

# 4. Nettoyer les processus orphelins
echo "4️⃣ Nettoyage des processus orphelins..."
sleep 2
pkill -9 -f "celery" 2>/dev/null || echo "Aucun processus Celery orphelin"

# 5. Vérification finale
echo "5️⃣ Vérification finale..."
echo "   Processus Celery restants:"
ps aux | grep -E "(celery|worker)" | grep -v grep | grep -v mdworker | grep -v fontworker || echo "   ✅ Aucun processus Celery"

echo "   Processus Python du projet:"
ps aux | grep -E "(python.*main\.py|uvicorn.*main)" | grep -v grep || echo "   ✅ Aucun processus Python du projet"

echo ""
echo "✅ ARRÊT COMPLET TERMINÉ !"
echo ""
echo "📋 Pour redémarrer proprement :"
echo "   1. Vérifiez votre fichier .env (MONDAY_API_TOKEN, etc.)"
echo "   2. Démarrez le worker : celery -A services.celery_app worker --loglevel=info"
echo "   3. Démarrez l'API : uvicorn main:app --reload --host 0.0.0.0 --port 8000"
echo "" 