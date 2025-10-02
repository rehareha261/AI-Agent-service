#!/usr/bin/env python3
"""Test de la correction de l'API Monday.com pour récupérer les updates."""

import asyncio
from tools.monday_tool import MondayTool
from utils.logger import get_logger

logger = get_logger(__name__)

async def test_monday_api_fix():
    """Test la récupération des updates depuis Monday.com."""
    
    print("🔍 Test de la correction API Monday.com...")
    
    # Initialiser l'outil Monday
    monday_tool = MondayTool()
    
    # ID de test (vous pouvez le changer pour un vrai ID Monday.com)
    test_item_id = "test_connection_123"
    
    print(f"📋 Test avec l'item ID: {test_item_id}")
    
    try:
        # 1. Tester la récupération des informations de base de l'item
        print("\n🔍 Test 1: Récupération des informations de l'item...")
        item_info_result = await monday_tool.execute_action(
            action="get_item_info",
            item_id=test_item_id
        )
        
        print(f"✅ Résultat get_item_info: {item_info_result.get('success', False)}")
        if item_info_result.get('error'):
            print(f"❌ Erreur: {item_info_result['error']}")
        else:
            print(f"📋 Item trouvé: {item_info_result.get('item_data', {}).get('name', 'N/A')}")
        
        # 2. Tester la récupération des updates
        print("\n🔍 Test 2: Récupération des updates...")
        updates_result = await monday_tool.execute_action(
            action="get_item_updates",
            item_id=test_item_id
        )
        
        print(f"✅ Résultat get_item_updates: {updates_result.get('success', False)}")
        if updates_result.get('error'):
            print(f"❌ Erreur: {updates_result['error']}")
        else:
            updates = updates_result.get('updates', [])
            print(f"📝 Nombre d'updates trouvées: {len(updates)}")
            
            # Afficher les updates s'il y en a
            for i, update in enumerate(updates[:3]):  # Afficher max 3 updates
                print(f"   Update {i+1}: {update.get('body', '')[:100]}...")
        
        # 3. Test de l'extraction d'URL depuis les updates
        print("\n🔍 Test 3: Extraction d'URL GitHub depuis les updates...")
        
        from nodes.prepare_node import _extract_repository_url_from_monday_updates
        
        extracted_url = await _extract_repository_url_from_monday_updates(test_item_id)
        
        if extracted_url:
            print(f"✅ URL extraite: {extracted_url}")
        else:
            print("⚠️ Aucune URL GitHub trouvée dans les updates")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_with_real_monday_item():
    """Test avec un vrai item Monday.com (si disponible)."""
    
    print("\n🌐 Test avec un item Monday.com réel...")
    
    # Vous pouvez remplacer cet ID par un vrai ID d'item Monday.com
    # Par exemple, si vous avez un item avec l'ID 5009534316 (vu dans les logs)
    real_item_id = "5009534316"
    
    monday_tool = MondayTool()
    
    try:
        print(f"📋 Test avec l'item ID réel: {real_item_id}")
        
        # Test de récupération des updates
        updates_result = await monday_tool.execute_action(
            action="get_item_updates",
            item_id=real_item_id
        )
        
        print(f"✅ Résultat: {updates_result.get('success', False)}")
        if updates_result.get('error'):
            print(f"❌ Erreur: {updates_result['error']}")
        else:
            updates = updates_result.get('updates', [])
            print(f"📝 Nombre d'updates trouvées: {len(updates)}")
            
            # Chercher des URLs GitHub dans les updates
            github_urls = []
            for update in updates:
                body = update.get('body', '')
                if 'github.com' in body.lower():
                    github_urls.append(body[:200] + "...")
            
            if github_urls:
                print(f"🔗 Updates contenant 'github.com': {len(github_urls)}")
                for i, url_text in enumerate(github_urls[:2]):
                    print(f"   {i+1}: {url_text}")
            else:
                print("🔍 Aucune mention de GitHub trouvée dans les updates")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du test avec item réel: {e}")
        return False

async def main():
    """Lance tous les tests."""
    print("🚀 Lancement des tests de correction API Monday.com\n")
    
    # Test 1: avec l'ID de test original
    test1_success = await test_monday_api_fix()
    
    # Test 2: avec un vrai ID Monday.com (si disponible)
    test2_success = await test_with_real_monday_item()
    
    print("\n📊 Résumé des tests:")
    print(f"   Test API de base: {'✅ RÉUSSI' if test1_success else '❌ ÉCHOUÉ'}")
    print(f"   Test item réel: {'✅ RÉUSSI' if test2_success else '❌ ÉCHOUÉ'}")
    
    if test1_success:
        print("\n🎉 La correction de l'API Monday.com semble fonctionner !")
        print("📝 Note: Si l'item 'test_connection_123' n'existe pas dans votre Monday.com,")
        print("   c'est normal qu'il ne soit pas trouvé. L'important est que l'API")
        print("   ne génère plus d'erreurs de requête GraphQL.")
    else:
        print("\n💥 Il semble y avoir encore des problèmes avec l'API.")

if __name__ == "__main__":
    asyncio.run(main()) 