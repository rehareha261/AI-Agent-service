#!/usr/bin/env python3
"""Test complet des réponses humaines dans le workflow de validation Monday.com."""

import asyncio
from datetime import datetime, timedelta, timezone
from graph.workflow_graph import _should_merge_or_debug_after_monday_validation
from services.intelligent_reply_analyzer import intelligent_reply_analyzer
from models.state import GraphState

async def test_human_responses():
    """Test toutes les réponses humaines possibles."""
    
    print("🧪 Test complet des réponses humaines dans le workflow")
    
    # Test cases: réponse humaine → décision attendue → action workflow attendue
    test_cases = [
        # Cas 1: "oui" avec pas de problèmes → merge
        {
            "human_reply": "oui",
            "has_problems": False,
            "expected_decision": "approve",
            "expected_workflow_action": "merge",
            "description": "Approbation avec aucun problème"
        },
        
        # Cas 2: "oui" avec problèmes → debug forcé
        {
            "human_reply": "oui", 
            "has_problems": True,
            "expected_decision": "approve",
            "expected_workflow_action": "debug",
            "description": "Approbation mais problèmes détectés → debug automatique"
        },
        
        # Cas 3: "non" → debug
        {
            "human_reply": "non",
            "has_problems": False,
            "expected_decision": "reject", 
            "expected_workflow_action": "debug",
            "description": "Rejet explicite → debug"
        },
        
        # Cas 4: "debug" → debug
        {
            "human_reply": "debug",
            "has_problems": False,
            "expected_decision": "reject",
            "expected_workflow_action": "debug", 
            "description": "Demande debug explicite → debug"
        },
        
        # Cas 5: "ok" avec problèmes → debug forcé
        {
            "human_reply": "ok",
            "has_problems": True,
            "expected_decision": "approve",
            "expected_workflow_action": "debug",
            "description": "OK mais problèmes → debug automatique"
        },
        
        # Cas 6: "valide" sans problèmes → merge
        {
            "human_reply": "valide",
            "has_problems": False,
            "expected_decision": "approve",
            "expected_workflow_action": "merge",
            "description": "Validation claire sans problèmes → merge"
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        print(f"\n{'='*60}")
        print(f"🧪 TEST {i+1}: {test_case['description']}")
        print(f"   Reply: '{test_case['human_reply']}'")
        print(f"   Problèmes: {'Oui' if test_case['has_problems'] else 'Non'}")
        
        # 1. Tester l'analyseur intelligent
        decision = await intelligent_reply_analyzer.analyze_human_intention(test_case['human_reply'])
        print(f"   🧠 Analyse IA: {decision.decision.value} (confiance: {decision.confidence})")
        
        decision_matches = decision.decision.value == test_case['expected_decision']
        print(f"   ✅ Décision correcte: {decision_matches}")
        
        # 2. Créer un état de workflow simulé
        state = {
            "results": {
                "human_decision": "approve" if decision.decision.value == "approve" else "debug",
                "should_merge": decision.decision.value == "approve",
                "human_validation_status": "approved" if decision.decision.value == "approve" else "rejected",
                "ai_messages": []
            }
        }
        
        # Simuler les problèmes si nécessaire
        if test_case['has_problems']:
            state["results"].update({
                "test_results": {"success": False, "failed_tests": ["test_example"]},
                "error_logs": ["Erreur de build"],
                "pr_url": None,  # PR non créée
                "qa_results": {"overall_score": 65}  # Score bas
            })
        else:
            state["results"].update({
                "test_results": {"success": True, "failed_tests": []},
                "error_logs": [],
                "pr_url": "https://github.com/test/repo/pull/123",
                "qa_results": {"overall_score": 85}
            })
        
        # 3. Tester la logique de workflow
        workflow_action = _should_merge_or_debug_after_monday_validation(state)
        print(f"   🔄 Action workflow: {workflow_action}")
        
        workflow_matches = workflow_action == test_case['expected_workflow_action']
        print(f"   ✅ Action correcte: {workflow_matches}")
        
        # 4. Vérifier les messages explicatifs
        if test_case['has_problems'] and test_case['human_reply'] in ['oui', 'ok', 'valide']:
            forced_debug = state["results"].get("forced_debug_reason")
            if forced_debug:
                print(f"   ⚠️ Debug forcé: {forced_debug}")
            else:
                print(f"   ❌ Debug forcé manquant!")
        
        # 5. Résultat du test
        overall_success = decision_matches and workflow_matches
        status_emoji = "✅" if overall_success else "❌"
        print(f"   {status_emoji} RÉSULTAT: {'SUCCÈS' if overall_success else 'ÉCHEC'}")
        
        if not overall_success:
            print(f"   ❌ Problèmes détectés:")
            if not decision_matches:
                print(f"      - Décision: attendu '{test_case['expected_decision']}', reçu '{decision.decision.value}'")
            if not workflow_matches:
                print(f"      - Workflow: attendu '{test_case['expected_workflow_action']}', reçu '{workflow_action}'")

async def test_edge_cases():
    """Test des cas particuliers et edge cases."""
    
    print(f"\n{'='*60}")
    print("🔧 Test des cas particuliers")
    
    edge_cases = [
        "❌",  # Emoji rejet
        "✅",  # Emoji approbation
        "peut-être",  # Ambiguë
        "je ne sais pas",  # Unclear
        "pourquoi ça ne marche pas?",  # Question
        "",  # Vide
        "🤖🔧🚀",  # Que des emojis
    ]
    
    for reply in edge_cases:
        print(f"\n🧪 Test edge case: '{reply}'")
        try:
            decision = await intelligent_reply_analyzer.analyze_human_intention(reply)
            print(f"   Résultat: {decision.decision.value} (conf: {decision.confidence:.2f})")
        except Exception as e:
            print(f"   ❌ Erreur: {e}")

if __name__ == "__main__":
    asyncio.run(test_human_responses())
    asyncio.run(test_edge_cases()) 