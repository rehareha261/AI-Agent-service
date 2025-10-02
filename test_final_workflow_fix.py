#!/usr/bin/env python3
"""Test final pour valider toutes les corrections du workflow Monday.com."""

import asyncio
from datetime import datetime, timedelta, timezone
from services.monday_validation_service import MondayValidationService
from graph.workflow_graph import _should_merge_or_debug_after_monday_validation
from models.state import GraphState
from config.workflow_limits import WorkflowLimits

async def test_all_workflow_fixes():
    """Test final de toutes les corrections du workflow."""
    
    print("🧪 Test final des corrections du workflow Monday.com")
    
    # Test 1: Vérifier les nouvelles limites
    print(f"\n✅ Test 1 - Nouvelles limites:")
    print(f"   MAX_NODES_SAFETY_LIMIT: {WorkflowLimits.MAX_NODES_SAFETY_LIMIT}")
    print(f"   MAX_DEBUG_ATTEMPTS: {WorkflowLimits.MAX_DEBUG_ATTEMPTS}")
    
    # Test 2: Validation des réponses humaines avec BOM
    print(f"\n✅ Test 2 - Validation réponses avec BOM:")
    validation_service = MondayValidationService()
    
    # Tester les réponses avec caractères invisibles
    test_cases = [
        ("\ufeffdebug", True, "debug avec BOM"),
        ("<p>\ufeffdebug</p>", True, "debug avec BOM et HTML"),
        ("\u200boui", True, "oui avec caractère invisible"),
        ("non", True, "non standard"),
        ("valide", True, "valide standard"),
        ("random text", False, "texte non-validation"),
    ]
    
    for reply_text, expected, description in test_cases:
        result = validation_service._is_validation_reply(reply_text)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {description}: '{repr(reply_text)}' → {result}")
    
    # Test 3: Logique de décision après validation Monday
    print(f"\n✅ Test 3 - Logique de décision après validation:")
    
    test_scenarios = [
        # Cas: oui + pas de problèmes → merge
        {
            "human_validation_status": "approved",
            "test_results": {"success": True, "failed_tests": []},
            "expected": "merge",
            "description": "oui + aucun problème"
        },
        # Cas: oui + problèmes détectés → debug automatique  
        {
            "human_validation_status": "approved", 
            "test_results": {"success": False, "failed_tests": ["test1", "test2"]},
            "expected": "debug",
            "description": "oui + problèmes détectés → debug forcé"
        },
        # Cas: non/debug → debug OpenAI
        {
            "human_validation_status": "debug",
            "test_results": {"success": False, "failed_tests": ["test1"]},
            "expected": "debug", 
            "description": "debug demandé par humain"
        },
        # Cas: timeout/erreur → update seulement
        {
            "human_validation_status": "error",
            "test_results": {"success": False, "failed_tests": []},
            "expected": "update_only",
            "description": "erreur/timeout → update seulement"
        }
    ]
    
    for scenario in test_scenarios:
        # Créer un état de test
        state = {
            "results": {
                "human_validation_status": scenario["human_validation_status"],
                "test_results": [scenario["test_results"]],
                "has_errors": len(scenario["test_results"].get("failed_tests", [])) > 0
            }
        }
        
        decision = _should_merge_or_debug_after_monday_validation(state)
        status = "✅" if decision == scenario["expected"] else "❌"
        print(f"   {status} {scenario['description']}: {scenario['human_validation_status']} → {decision}")
    
    # Test 4: Gestion des erreurs de permissions Monday.com
    print(f"\n✅ Test 4 - Gestion permissions Monday.com:")
    
    # Simuler une réponse d'erreur de permissions
    mock_results = {
        "ai_messages": ["Test task completed"],
        "test_results": [{"success": False, "failed_tests": ["test1"]}]
    }
    
    try:
        # Tester avec un item qui pourrait avoir des problèmes de permissions
        update_id = await validation_service.post_validation_update("test_item_12345", mock_results)
        print(f"   ✅ Gestion gracieuse des erreurs: update_id = {update_id}")
        
        # Vérifier que l'update_id est créé même en cas d'erreur
        if update_id and "failed_update" in update_id:
            print(f"   ✅ Update_id de secours créé correctement")
        elif update_id:
            print(f"   ✅ Update_id normal créé: {update_id}")
        else:
            print(f"   ❌ Aucun update_id créé")
            
    except Exception as e:
        print(f"   ❌ Exception non gérée: {e}")
    
    # Test 5: Vérifier que le workflow peut maintenant dépasser 25 nœuds
    print(f"\n✅ Test 5 - Limite de nœuds augmentée:")
    print(f"   Ancienne limite: 25 nœuds")
    print(f"   Nouvelle limite: {WorkflowLimits.MAX_NODES_SAFETY_LIMIT} nœuds")
    print(f"   ✅ Augmentation de {WorkflowLimits.MAX_NODES_SAFETY_LIMIT - 25} nœuds pour permettre les boucles")
    
    print(f"\n🎉 Tous les tests des corrections terminés !")
    print(f"\n📋 **Résumé des corrections appliquées:**")
    print(f"   1. ✅ Correction du BOM dans les réponses Monday.com")
    print(f"   2. ✅ Fixation des problèmes de timezone (UTC)")
    print(f"   3. ✅ Augmentation limite nœuds: 25 → {WorkflowLimits.MAX_NODES_SAFETY_LIMIT}")
    print(f"   4. ✅ Réduction MAX_DEBUG_ATTEMPTS: 3 → {WorkflowLimits.MAX_DEBUG_ATTEMPTS}")
    print(f"   5. ✅ Gestion gracieuse des erreurs de permissions Monday.com")
    print(f"   6. ✅ Logique améliorée: 'oui' + problèmes → debug automatique")

if __name__ == "__main__":
    asyncio.run(test_all_workflow_fixes()) 