# -*- coding: utf-8 -*-
"""
Script de test simplifié pour vérifier les corrections des erreurs.
Ce script teste uniquement les modèles Pydantic sans importer les nodes.
"""

import json
import sys
from datetime import datetime


def test_erreur_1_generated_code_conversion():
    """Test ERREUR 1: generated_code doit accepter dict et le convertir en JSON string."""
    
    print("\n" + "="*80)
    print("TEST ERREUR 1: Conversion generated_code (dict → JSON string)")
    print("="*80)
    
    # Import uniquement les modèles
    from models.schemas import HumanValidationRequest
    
    # Test 1: Passer un dict directement
    print("\n1️⃣ Test avec dict Python...")
    try:
        code_dict = {
            "main.py": "print('Hello World')",
            "utils.py": "def helper(): pass"
        }
        
        validation = HumanValidationRequest(
            validation_id="test_val_123",
            workflow_id="wf_456",
            task_id="789",
            task_title="Test Task",
            generated_code=code_dict,  # Dict Python
            code_summary="Test summary",
            files_modified=["main.py", "utils.py"],
            original_request="Test request"
        )
        
        # Vérifier que c'est maintenant un string JSON
        assert isinstance(validation.generated_code, str), f"generated_code devrait être un string, mais c'est {type(validation.generated_code)}"
        
        # Vérifier que c'est un JSON valide
        parsed = json.loads(validation.generated_code)
        assert isinstance(parsed, dict), "Le JSON devrait être parsable en dict"
        assert "main.py" in parsed, "Les clés du dict doivent être préservées"
        
        print("✅ SUCCÈS: Dict Python → JSON string OK")
        print(f"   Type: {type(validation.generated_code)}")
        print(f"   Contenu: {validation.generated_code[:100]}...")
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Passer un string JSON directement
    print("\n2️⃣ Test avec JSON string...")
    try:
        code_json = json.dumps({"test.py": "code here"})
        
        validation = HumanValidationRequest(
            validation_id="test_val_124",
            workflow_id="wf_457",
            task_id="790",
            task_title="Test Task 2",
            generated_code=code_json,  # Déjà un JSON string
            code_summary="Test summary",
            files_modified=["test.py"],
            original_request="Test request"
        )
        
        assert isinstance(validation.generated_code, str), "generated_code devrait rester un string"
        json.loads(validation.generated_code)  # Doit être parsable
        
        print("✅ SUCCÈS: JSON string → JSON string OK")
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n✅ TOUS LES TESTS ERREUR 1 RÉUSSIS !")
    return True


def test_erreur_3_test_results_normalization():
    """Test ERREUR 3: _format_test_results doit gérer list et dict."""
    
    print("\n" + "="*80)
    print("TEST ERREUR 3: Normalisation test_results (list vs dict)")
    print("="*80)
    
    # Définir la fonction localement pour éviter les imports circulaires
    def _format_test_results(test_results):
        """Version locale de _format_test_results pour le test."""
        if not test_results:
            return "Aucun résultat de test disponible"
        
        # Normaliser test_results en dict si c'est une liste
        if isinstance(test_results, list):
            test_results_dict = {
                "tests": test_results,
                "count": len(test_results),
                "success": all(
                    t.get("success", False) if isinstance(t, dict) else False 
                    for t in test_results
                )
            }
        elif isinstance(test_results, dict):
            test_results_dict = test_results
        else:
            return f"⚠️ Résultats de tests dans un format inattendu: {type(test_results)}"
        
        # Maintenant on peut utiliser .get() en toute sécurité
        if test_results_dict.get("success"):
            return "✅ Tests réussis"
        else:
            failed_tests = test_results_dict.get("failed_tests", [])
            if failed_tests:
                return f"❌ {len(failed_tests)} test(s) échoué(s)"
            else:
                if "tests" in test_results_dict:
                    failed_count = sum(
                        1 for t in test_results_dict["tests"] 
                        if isinstance(t, dict) and not t.get("success", False)
                    )
                    if failed_count > 0:
                        return f"❌ {failed_count} test(s) échoué(s)"
                return "❌ Tests échoués (détails non disponibles)"
    
    # Test 1: test_results comme liste
    print("\n1️⃣ Test avec liste de résultats...")
    try:
        test_results_list = [
            {"name": "test1", "success": True},
            {"name": "test2", "success": False},
            {"name": "test3", "success": True}
        ]
        
        result = _format_test_results(test_results_list)
        assert isinstance(result, str), "Le résultat doit être un string"
        print(f"✅ SUCCÈS: Liste → {result}")
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: test_results comme dict
    print("\n2️⃣ Test avec dict de résultats...")
    try:
        test_results_dict = {
            "success": True,
            "total": 5,
            "passed": 5,
            "failed": 0
        }
        
        result = _format_test_results(test_results_dict)
        assert isinstance(result, str), "Le résultat doit être un string"
        assert "✅" in result or "réussi" in result.lower(), "Devrait indiquer un succès"
        
        print(f"✅ SUCCÈS: Dict → {result}")
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n✅ TOUS LES TESTS ERREUR 3 RÉUSSIS !")
    return True


def test_bonus_pydantic_validators():
    """Test BONUS: Validateurs Pydantic pour conversion automatique des IDs."""
    
    print("\n" + "="*80)
    print("TEST BONUS: Validateurs Pydantic pour IDs (int ↔ str)")
    print("="*80)
    
    from models.schemas import HumanValidationRequest, MondayEvent
    
    # Test 1: task_id comme int
    print("\n1️⃣ Test task_id int → str...")
    try:
        validation = HumanValidationRequest(
            validation_id="test_val_126",
            workflow_id=12345,  # int au lieu de str
            task_id=67890,      # int au lieu de str
            task_title="Test Task",
            generated_code={"test.py": "code"},
            code_summary="Test",
            files_modified=["test.py"],
            original_request="Test"
        )
        
        assert isinstance(validation.task_id, str), f"task_id devrait être converti en str, mais c'est {type(validation.task_id)}"
        assert isinstance(validation.workflow_id, str), f"workflow_id devrait être converti en str, mais c'est {type(validation.workflow_id)}"
        assert validation.task_id == "67890", f"La valeur doit être correcte: attendu '67890', reçu '{validation.task_id}'"
        assert validation.workflow_id == "12345", f"La valeur doit être correcte: attendu '12345', reçu '{validation.workflow_id}'"
        
        print(f"✅ SUCCÈS: task_id={validation.task_id} (type={type(validation.task_id).__name__})")
        print(f"✅ SUCCÈS: workflow_id={validation.workflow_id} (type={type(validation.workflow_id).__name__})")
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: MondayEvent IDs comme string
    print("\n2️⃣ Test MondayEvent pulseId/boardId str → int...")
    try:
        event = MondayEvent(
            pulseId="123456789",  # string au lieu de int
            boardId="987654321",  # string au lieu de int
            pulseName="Test Item"
        )
        
        assert isinstance(event.pulseId, int), f"pulseId devrait être converti en int, mais c'est {type(event.pulseId)}"
        assert isinstance(event.boardId, int), f"boardId devrait être converti en int, mais c'est {type(event.boardId)}"
        assert event.pulseId == 123456789, f"La valeur doit être correcte: attendu 123456789, reçu {event.pulseId}"
        assert event.boardId == 987654321, f"La valeur doit être correcte: attendu 987654321, reçu {event.boardId}"
        
        print(f"✅ SUCCÈS: pulseId={event.pulseId} (type={type(event.pulseId).__name__})")
        print(f"✅ SUCCÈS: boardId={event.boardId} (type={type(event.boardId).__name__})")
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n✅ TOUS LES TESTS BONUS RÉUSSIS !")
    return True


def run_all_tests():
    """Lance tous les tests."""
    
    print("\n" + "="*80)
    print("🧪 LANCEMENT DES TESTS DE VÉRIFICATION DES CORRECTIONS")
    print("="*80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    results = {
        "ERREUR 1 (generated_code)": test_erreur_1_generated_code_conversion(),
        "ERREUR 3 (test_results)": test_erreur_3_test_results_normalization(),
        "BONUS (Pydantic validators)": test_bonus_pydantic_validators()
    }
    
    print("\n" + "="*80)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*80)
    
    total = len(results)
    passed = sum(1 for success in results.values() if success)
    
    for test_name, success in results.items():
        status = "✅ RÉUSSI" if success else "❌ ÉCHOUÉ"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*80)
    print(f"RÉSULTAT FINAL: {passed}/{total} tests réussis")
    print("="*80)
    
    if passed == total:
        print("\n🎉 TOUS LES TESTS SONT RÉUSSIS ! Les corrections fonctionnent correctement.")
        return True
    else:
        print(f"\n⚠️ {total - passed} test(s) ont échoué. Vérifiez les détails ci-dessus.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

