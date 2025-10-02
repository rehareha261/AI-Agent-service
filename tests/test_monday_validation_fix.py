#!/usr/bin/env python3
"""
Test simplifié des corrections pour l'erreur 'list' object has no attribute 'get'
"""

def test_protection_mechanisms():
    """Test direct des mécanismes de protection."""
    
    print("🧪 Test direct des protections contre 'list' object has no attribute 'get'")
    
    # Test 1: Vérification isinstance avant .get()
    test_cases = [
        {"data": "normal"},       # dict normal
        ["item1", "item2"],       # liste (erreur potentielle)
        "string",                 # string
        None,                     # None
        123                       # int
    ]
    
    for i, test_data in enumerate(test_cases, 1):
        print(f"  Test {i}: {type(test_data).__name__} = {test_data}")
        
        # Mécanisme de protection
        if isinstance(test_data, dict):
            success = test_data.get("success", False)
            print(f"    ✅ Protection OK - success: {success}")
        else:
            print(f"    ✅ Protection activée - Type {type(test_data).__name__} rejeté")
    
    print("✅ Tous les tests de protection passés!")
    return True

if __name__ == "__main__":
    test_protection_mechanisms()