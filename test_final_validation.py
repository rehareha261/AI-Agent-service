#!/usr/bin/env python3
"""Test final pour valider la correction complète de la validation Monday.com."""

import asyncio
from datetime import datetime, timedelta, timezone
from services.monday_validation_service import MondayValidationService

async def test_final_validation():
    """Test final du workflow de validation Monday.com."""
    
    print("🎯 Test final du workflow de validation Monday.com")
    
    validation_service = MondayValidationService()
    item_id = "5010214993"
    validation_update_id = "463763339"
    
    try:
        print(f"\n📥 Récupération des updates pour item {item_id}...")
        updates = await validation_service._get_item_updates(item_id)
        
        # Trouver le timestamp de la reply debug
        debug_reply_time = None
        for update in updates:
            if (update.get('type') == 'reply' and 
                update.get('parent_id') == validation_update_id and
                validation_service._is_validation_reply(update.get('body', ''))):
                debug_reply_time_str = update.get('created_at')
                debug_reply_time = datetime.fromisoformat(debug_reply_time_str.replace('Z', '+00:00'))
                print(f"✅ Reply debug trouvée à {debug_reply_time}")
                break
        
        if not debug_reply_time:
            print("❌ Reply debug non trouvée")
            return
        
        # Créer une validation "depuis" 10 minutes AVANT la reply debug
        # Cela simule le cas où Celery lance la validation, puis l'humain répond
        since_time = debug_reply_time - timedelta(minutes=10)
        
        print(f"\n🎯 Test avec validation depuis {since_time}")
        print(f"   Reply debug créée à {debug_reply_time}")
        
        # Simuler la validation pending avec le bon timestamp
        validation_service.pending_validations[validation_update_id] = {
            "item_id": item_id,
            "created_at": since_time,
            "status": "pending"
        }
        
        # Test direct de _find_human_reply avec les bons paramètres
        print(f"\n🧪 Test direct de _find_human_reply...")
        reply = validation_service._find_human_reply(
            original_update_id=validation_update_id,
            updates=updates,
            since=since_time
        )
        
        if reply:
            print(f"✅ Reply trouvée directement!")
            print(f"   ID: {reply.get('id')}")
            print(f"   Body: {repr(reply.get('body', ''))}")
            
            # Analyser la reply
            from services.intelligent_reply_analyzer import intelligent_reply_analyzer
            analysis = await intelligent_reply_analyzer.analyze_human_intention(reply.get('body', ''))
            print(f"   Analyse: {analysis.decision.value} (confiance: {analysis.confidence})")
            
            if analysis.decision.value == "reject":
                print(f"🎉 SUCCESS: La reply 'debug' est correctement identifiée comme REJECT!")
            else:
                print(f"❌ Problème: analyse inattendue")
        else:
            print(f"❌ Reply non trouvée directement")
        
        # Test complet avec check_for_human_replies (timeout court)
        print(f"\n🎯 Test complet avec check_for_human_replies...")
        response = await validation_service.check_for_human_replies(
            update_id=validation_update_id,
            timeout_minutes=0.1  # 6 secondes seulement
        )
        
        if response and response.status.value != "expired":
            print(f"✅ Workflow complet réussi!")
            print(f"   Status: {response.status.value}")
            print(f"   Should merge: {response.should_merge}")
            print(f"   Analysis confidence: {getattr(response, 'analysis_confidence', 'N/A')}")
            
            if response.status.value == "rejected" and not response.should_merge:
                print(f"🎉 CORRECTION COMPLÈTEMENT VALIDÉE!")
                print(f"   ✅ Reply 'debug' détectée")
                print(f"   ✅ Analysée comme 'reject'") 
                print(f"   ✅ Should merge = False")
                print(f"   ✅ Workflow peut continuer vers debug")
            else:
                print(f"❌ Valeurs inattendues")
        else:
            print(f"❌ Workflow complet échoué (timeout/erreur)")
            
    except Exception as e:
        print(f"❌ Erreur durant le test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_final_validation()) 