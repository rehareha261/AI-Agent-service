#!/usr/bin/env python3
"""Test corrigé Celery + RabbitMQ"""

from services.celery_app import celery_app
import time

def test_celery_connection():
    try:
        print("🔍 Test de connexion Celery vers RabbitMQ...")
        
        # Vérifier la configuration
        print(f"📋 Broker URL: {celery_app.conf.broker_url}")
        print(f"📋 Result Backend: {celery_app.conf.result_backend}")
        
        # Tester l'envoi d'une tâche VALIDE
        print("🚀 Envoi d'une tâche test VALIDE...")
        
        result = celery_app.send_task(
            "ai_agent_background.execute_workflow",
            kwargs={"task_request_dict": {
                "task_id": "test_connection_123",
                "title": "Test de connexion RabbitMQ",
                "description": "Test de validation de la connexion Celery-RabbitMQ",
                "task_type": "testing",  # ✅ Type valide
                "priority": "low"
            }},
            priority=5
        )
        
        print(f"✅ Tâche envoyée - ID: {result.id}")
        print("⏳ Attente de 5 secondes...")
        time.sleep(5)
        
        # Vérifier le statut
        print(f"📊 Statut tâche: {result.status}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur Celery: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_celery_connection()