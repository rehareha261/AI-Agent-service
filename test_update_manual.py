#!/usr/bin/env python3
import asyncio
from services.webhook_persistence_service import webhook_persistence
from services.database_persistence_service import db_persistence

async def test_update_event():
    await db_persistence.initialize()
    
    # Simuler un webhook create_update
    payload = {
        "event": {
            "type": "create_update",
            "pulseId": 5039108740,  # REMPLACER par votre item ID
            "textBody": "Bonjour, pouvez-vous ajouter un export CSV ?",
            "updateId": "test_update_manual_001"
        }
    }
    
    print("🧪 Test simulation webhook update...")
    result = await webhook_persistence.process_monday_webhook(payload)
    
    print(f"\n✅ Résultat: {result}")

if __name__ == "__main__":
    asyncio.run(test_update_event())
