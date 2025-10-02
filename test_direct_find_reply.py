#!/usr/bin/env python3
"""Test direct de _find_human_reply."""

import asyncio
from datetime import datetime, timedelta, timezone
from services.monday_validation_service import MondayValidationService

async def test_find_human_reply():
    """Test direct de _find_human_reply."""
    
    print("🧪 Test direct de _find_human_reply")
    
    validation_service = MondayValidationService()
    item_id = "5010214993"
    
    # Récupérer les updates
    updates = await validation_service._get_item_updates(item_id)
    print(f"✅ {len(updates)} updates récupérées")
    
    # Identifier les IDs
    validation_update_id = "463763339"
    
    # Test avec différents "since" times
    test_times = [
        datetime.now(timezone.utc) - timedelta(hours=1),  # 1h avant
        datetime.now(timezone.utc) - timedelta(minutes=30),  # 30 min avant
        datetime.now(timezone.utc) - timedelta(minutes=15),  # 15 min avant
        datetime(2025, 9, 24, 10, 20, 0),  # Timestamp spécifique (sera converti par la fonction)
    ]
    
    for i, since_time in enumerate(test_times):
        print(f"\n🧪 Test {i+1}: Since {since_time}")
        
        result = validation_service._find_human_reply(
            original_update_id=validation_update_id,
            updates=updates,
            since=since_time
        )
        
        if result:
            print(f"✅ Reply trouvée: {result.get('id')}")
            print(f"   Body: {repr(result.get('body', ''))}")
            print(f"   Parent: {result.get('parent_id')}")
            print(f"   Time: {result.get('created_at')}")
        else:
            print(f"❌ Aucune reply trouvée")
            
            # Debug détaillé
            print(f"   Debug: recherche replies à {validation_update_id} depuis {since_time}")
            for update in updates:
                if update.get('type') == 'reply':
                    update_time_str = update.get("created_at")
                    try:
                        update_time = datetime.fromisoformat(update_time_str.replace('Z', '+00:00'))
                        is_after = update_time > since_time
                        matches_parent = (update.get("reply_to_id") == validation_update_id or 
                                        update.get("parent_id") == validation_update_id)
                        is_validation = validation_service._is_validation_reply(update.get('body', ''))
                        
                        print(f"     Reply {update.get('id')}: time={update_time} (after={is_after}), parent_match={matches_parent}, is_valid={is_validation}")
                        print(f"       Body: {repr(update.get('body', ''))[:30]}")
                    except Exception as e:
                        print(f"     Reply {update.get('id')}: time parsing error: {e}")

if __name__ == "__main__":
    asyncio.run(test_find_human_reply()) 