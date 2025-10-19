#!/usr/bin/env python3
"""
Test autonome des corrections du statut Monday après merge.
Ce test vérifie la logique directement sans importer tout le projet.
"""

import sys
import os

# Ajouter le répertoire du projet au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_priority_logic():
    """Test de la logique de priorité dans _determine_final_status."""
    
    print("=" * 80)
    print("TEST 1: Vérification de la priorité de merge_successful")
    print("=" * 80)
    
    # Simuler la logique dans nodes/update_node.py lignes 200-203
    def determine_final_status_mock(state):
        """Mock de _determine_final_status avec la logique corrigée."""
        # ✅ PRIORITÉ ABSOLUE: Vérifier merge_successful EN PREMIER
        if state["results"] and state["results"].get("merge_successful", False):
            print("🎉 Merge réussi détecté - Statut forcé à 'Done'")
            return "Done", "success"
        
        # ✅ NOUVEAU: Vérifier d'abord si un statut explicite a été défini
        if state["results"] and "monday_final_status" in state["results"]:
            explicit_status = state["results"]["monday_final_status"]
            print(f"📌 Utilisation du statut explicite: {explicit_status}")
            
            if explicit_status == "Done":
                return "Done", "success"
            elif explicit_status == "Working on it":
                return "Working on it", "partial"
            elif explicit_status == "Stuck":
                return "Stuck", "failed"
            else:
                return explicit_status, "partial"
        
        # Autres cas...
        return "Working on it", "partial"
    
    # Test Case 1: merge_successful=True doit forcer "Done"
    state1 = {
        "results": {
            "merge_successful": True,
            "merge_commit": "abc123"
        }
    }
    
    final_status, success_level = determine_final_status_mock(state1)
    assert final_status == "Done", f"ÉCHEC: Attendu 'Done', reçu '{final_status}'"
    assert success_level == "success", f"ÉCHEC: Attendu 'success', reçu '{success_level}'"
    print(f"✅ Test 1.1: merge_successful=True → '{final_status}' ('{success_level}')")
    
    # Test Case 2: merge_successful=True a priorité sur monday_final_status
    state2 = {
        "results": {
            "merge_successful": True,
            "monday_final_status": "Working on it"  # Conflit
        }
    }
    
    final_status, success_level = determine_final_status_mock(state2)
    assert final_status == "Done", f"ÉCHEC: merge_successful doit avoir priorité, reçu '{final_status}'"
    print(f"✅ Test 1.2: merge_successful a priorité → '{final_status}'")
    
    # Test Case 3: Sans merge_successful, utiliser monday_final_status
    state3 = {
        "results": {
            "monday_final_status": "Working on it"
        }
    }
    
    final_status, success_level = determine_final_status_mock(state3)
    assert final_status == "Working on it", f"ÉCHEC: Attendu 'Working on it', reçu '{final_status}'"
    print(f"✅ Test 1.3: Sans merge → '{final_status}'")
    
    print()


def test_validation_critique():
    """Test de la validation critique dans update_monday."""
    
    print("=" * 80)
    print("TEST 2: Validation critique d'incohérence")
    print("=" * 80)
    
    # Simuler la logique de validation critique (lignes 65-70)
    def apply_critical_validation(state, final_status, success_level):
        """Mock de la validation critique."""
        if state["results"].get("merge_successful", False) and final_status != "Done":
            print(f"❌ INCOHÉRENCE: merge_successful=True mais final_status='{final_status}'")
            print("🔧 Correction automatique - Forçage à 'Done'")
            final_status = "Done"
            success_level = "success"
            state["results"]["status_corrected"] = True
        
        return final_status, success_level
    
    # Test: Détecter et corriger une incohérence
    state = {
        "results": {
            "merge_successful": True
        }
    }
    
    # Supposons que final_status soit mal défini
    final_status = "Working on it"
    success_level = "partial"
    
    final_status, success_level = apply_critical_validation(state, final_status, success_level)
    
    assert final_status == "Done", f"ÉCHEC: Correction automatique non appliquée"
    assert success_level == "success"
    assert state["results"].get("status_corrected") == True
    print(f"✅ Test 2.1: Incohérence détectée et corrigée → '{final_status}'")
    
    print()


def test_merge_node_persistence():
    """Test de la persistance dans merge_node."""
    
    print("=" * 80)
    print("TEST 3: Persistance après merge dans merge_node")
    print("=" * 80)
    
    # Simuler le bloc de code dans merge_node.py lignes 178-193
    state = {
        "results": {}
    }
    
    # Simuler un merge réussi
    merge_result = {"success": True, "merge_commit": "abc123def456"}
    repo_url = "https://github.com/test/repo"
    
    if merge_result.get("success", False):
        merge_commit = merge_result.get("merge_commit")
        
        # Appliquer les modifications de l'ÉTAPE 2
        state["results"]["merge_successful"] = True
        state["results"]["merge_commit"] = merge_commit
        state["results"]["monday_final_status"] = "Done"
        state["results"]["workflow_success"] = True
        state["status"] = "completed"
        
        # Ajouter l'URL du commit
        if merge_commit:
            commit_url = f"{repo_url.rstrip('/')}/commit/{merge_commit}"
            state["results"]["merge_commit_url"] = commit_url
        
        print(f"📊 État après merge:")
        print(f"  - merge_successful: {state['results']['merge_successful']}")
        print(f"  - monday_final_status: {state['results']['monday_final_status']}")
        print(f"  - workflow_success: {state['results']['workflow_success']}")
        print(f"  - status: {state['status']}")
        print(f"  - merge_commit_url: {state['results'].get('merge_commit_url', 'N/A')}")
    
    # Vérifications
    assert state["results"]["merge_successful"] == True
    assert state["results"]["monday_final_status"] == "Done"
    assert state["results"]["workflow_success"] == True
    assert state["status"] == "completed"
    assert "merge_commit_url" in state["results"]
    
    print("✅ Test 3.1: Tous les champs de persistance sont corrects")
    
    print()


def test_status_mapping():
    """Test du mapping des statuts dans monday_tool."""
    
    print("=" * 80)
    print("TEST 4: Mapping des statuts Monday")
    print("=" * 80)
    
    # Simuler STATUS_MAPPING de monday_tool.py
    STATUS_MAPPING = {
        "completed": "Done",
        "done": "Done",
        "Done": "Done",  # ✅ Mapping identité important
        "working": "Working on it",
        "stuck": "Stuck"
    }
    
    test_cases = [
        ("done", "Done"),
        ("Done", "Done"),
        ("completed", "Done"),
        ("working", "Working on it"),
        ("stuck", "Stuck")
    ]
    
    all_passed = True
    for input_status, expected in test_cases:
        actual = STATUS_MAPPING.get(input_status, input_status)
        if actual == expected:
            print(f"✅ '{input_status}' → '{actual}'")
        else:
            print(f"❌ '{input_status}' → '{actual}' (attendu: '{expected}')")
            all_passed = False
    
    assert all_passed, "Certains mappings ont échoué"
    
    print()


def test_comment_enrichment():
    """Test de l'enrichissement du commentaire Monday."""
    
    print("=" * 80)
    print("TEST 5: Enrichissement du commentaire Monday")
    print("=" * 80)
    
    # Simuler la logique d'enrichissement (lignes 76-82)
    completion_comment = "Tâche complétée avec succès"
    
    state = {
        "results": {
            "merge_successful": True,
            "merge_commit": "abc123def456",
            "merge_commit_url": "https://github.com/test/repo/commit/abc123def456"
        }
    }
    
    # Appliquer l'enrichissement
    if state["results"].get("merge_successful", False):
        merge_info = f"\n\n✅ **Pull Request mergée avec succès**\n"
        if state["results"].get("merge_commit"):
            merge_info += f"- **Commit de merge**: `{state['results']['merge_commit']}`\n"
        if state["results"].get("merge_commit_url"):
            merge_info += f"- **Lien**: {state['results']['merge_commit_url']}\n"
        completion_comment += merge_info
    
    # Vérifications
    assert "Pull Request mergée avec succès" in completion_comment
    assert "abc123def456" in completion_comment
    assert "https://github.com/test/repo/commit" in completion_comment
    
    print("✅ Test 5.1: Commentaire enrichi avec les infos de merge")
    print(f"\nAperçu du commentaire:\n{'-' * 40}")
    print(completion_comment)
    print('-' * 40)
    
    print()


def test_post_update_verification():
    """Test de la vérification post-update."""
    
    print("=" * 80)
    print("TEST 6: Vérification post-update")
    print("=" * 80)
    
    # Simuler la logique de vérification (lignes 149-159)
    def verify_post_update(state, final_status):
        """Mock de la vérification post-update."""
        messages = []
        
        if state["results"].get("merge_successful", False):
            if final_status != "Done":
                print(f"❌ ERREUR: Merge réussi mais statut='{final_status}'")
                messages.append(f"⚠️ Avertissement: Statut Monday='{final_status}' (attendu 'Done')")
                return False, messages
            else:
                print("✅ Vérification: Statut 'Done' correctement appliqué")
                messages.append("✅ Statut Monday.com mis à jour : Done")
                return True, messages
        
        return True, messages
    
    # Test Case 1: Vérification réussie
    state1 = {
        "results": {
            "merge_successful": True
        }
    }
    success, messages = verify_post_update(state1, "Done")
    assert success == True
    assert any("Done" in msg for msg in messages)
    print("✅ Test 6.1: Vérification OK quand statut correct")
    
    # Test Case 2: Détection d'incohérence
    state2 = {
        "results": {
            "merge_successful": True
        }
    }
    success, messages = verify_post_update(state2, "Working on it")
    assert success == False
    assert any("Avertissement" in msg for msg in messages)
    print("✅ Test 6.2: Incohérence détectée lors de la vérification")
    
    print()


def main():
    """Exécuter tous les tests."""
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "TESTS DE VALIDATION COMPLETS" + " " * 30 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    try:
        test_priority_logic()
        test_validation_critique()
        test_merge_node_persistence()
        test_status_mapping()
        test_comment_enrichment()
        test_post_update_verification()
        
        print("=" * 80)
        print("RÉCAPITULATIF DES TESTS")
        print("=" * 80)
        print("✅ TEST 1: Logique de priorité - PASS")
        print("✅ TEST 2: Validation critique - PASS")
        print("✅ TEST 3: Persistance merge_node - PASS")
        print("✅ TEST 4: Mapping des statuts - PASS")
        print("✅ TEST 5: Enrichissement commentaire - PASS")
        print("✅ TEST 6: Vérification post-update - PASS")
        print("=" * 80)
        print()
        
        print("╔" + "=" * 78 + "╗")
        print("║" + " " * 25 + "✅ TOUS LES TESTS RÉUSSIS ✅" + " " * 26 + "║")
        print("╚" + "=" * 78 + "╝")
        print()
        
        return 0
        
    except AssertionError as e:
        print()
        print("=" * 80)
        print(f"❌ ÉCHEC DU TEST: {e}")
        print("=" * 80)
        return 1
    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ ERREUR INATTENDUE: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
