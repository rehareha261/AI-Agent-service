#!/usr/bin/env python3
"""Test de la correction du BOM dans _is_validation_reply."""

import asyncio
from services.monday_validation_service import MondayValidationService

async def test_bom_fix():
    """Test de la correction du BOM."""
    
    validation_service = MondayValidationService()
    
    # Tests avec et sans BOM
    test_cases = [
        # Reply normale
        ("debug", True),
        ("<p>debug</p>", True),
        
        # Reply avec BOM
        ("\ufeffdebug", True),
        ("<p>\ufeffdebug</p>", True),
        
        # Autres caractères invisibles
        ("\u200bdebug", True),
        ("\u00a0debug", True),
        
        # Non-validation replies
        ("hello", False),
        ("<p>random text</p>", False),
    ]
    
    print("🧪 Test de correction BOM:")
    
    for i, (text, expected) in enumerate(test_cases):
        result = validation_service._is_validation_reply(text)
        status = "✅" if result == expected else "❌"
        print(f"{status} Test {i+1}: {repr(text)} -> {result} (attendu: {expected})")
    
    # Test spécifique avec le texte exact de Monday.com
    monday_debug_text = '<p>\ufeffdebug</p>'
    result = validation_service._is_validation_reply(monday_debug_text)
    print(f"\n🎯 Test spécifique Monday.com:")
    print(f"   Texte: {repr(monday_debug_text)}")
    print(f"   Résultat: {'✅ TROUVÉ' if result else '❌ PAS TROUVÉ'}")

if __name__ == "__main__":
    asyncio.run(test_bom_fix()) 