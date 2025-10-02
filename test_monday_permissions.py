#!/usr/bin/env python3
"""Script de diagnostic des permissions Monday.com."""

import asyncio
import sys
import os

# Ajouter le répertoire racine au path
sys.path.insert(0, os.path.dirname(__file__))

from tools.monday_tool import MondayTool
import json


async def test_monday_permissions():
    """Test des permissions Monday.com avec diagnostic complet."""
    
    print("🔍 Diagnostic des permissions Monday.com")
    print("=" * 50)
    
    # Initialiser l'outil Monday
    monday_tool = MondayTool()
    
    # ID de l'item de test (utiliser l'ID du dernier workflow)
    test_item_id = "5000034576"  # Item ID du dernier workflow d'après les logs
    
    try:
        # Exécuter le diagnostic
        print(f"📋 Test sur l'item: {test_item_id}")
        diagnostic = await monday_tool.diagnose_permissions(test_item_id)
        
        print("\n📊 RAPPORT DE DIAGNOSTIC:")
        print("=" * 30)
        
        for diagnosis in diagnostic["diagnosis"]:
            print(diagnosis)
        
        print("\n🔍 DÉTAILS TECHNIQUES:")
        print("=" * 25)
        print(json.dumps(diagnostic, indent=2, ensure_ascii=False))
        
        # Test spécifique de création d'update
        print("\n🧪 TEST CRÉATION UPDATE:")
        print("=" * 25)
        
        test_comment = "🤖 Test de permissions - Message automatique de diagnostic"
        comment_result = await monday_tool._arun(
            action="add_comment",
            item_id=test_item_id,
            comment=test_comment
        )
        
        if comment_result.get("success"):
            print("✅ Création d'update réussie!")
            print(f"   Comment ID: {comment_result.get('comment_id')}")
        else:
            print("❌ Échec création update:")
            print(f"   Erreur: {comment_result.get('error')}")
            
    except Exception as e:
        print(f"❌ Erreur lors du diagnostic: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_monday_permissions())
    sys.exit(0 if success else 1) 