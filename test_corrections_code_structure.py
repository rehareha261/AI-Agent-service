# -*- coding: utf-8 -*-
"""
Tests de structure du code pour verifier les corrections SIGSEGV.
Ces tests verifient que le code contient les corrections necessaires.
"""

import inspect
import sys


def test_1_finalize_node_has_langsmith_cleanup():
    """Test 1: finalize_node contient le nettoyage LangSmith."""
    print("\n[Test 1] Verification nettoyage LangSmith dans finalize_node...")
    
    try:
        # Lire le fichier directement pour eviter l'import circulaire
        with open("nodes/finalize_node.py", "r", encoding="utf-8") as f:
            source = f.read()
        
        checks = [
            ("langsmith_config._client = None", "Nettoyage du client"),
            ("CORRECTION SIGSEGV", "Commentaire de correction"),
            ("Nettoyage du client LangSmith", "Log de nettoyage")
        ]
        
        all_passed = True
        for check_str, description in checks:
            if check_str in source:
                print(f"  ✅ {description}: trouve")
            else:
                print(f"  ❌ {description}: MANQUANT")
                all_passed = False
        
        if all_passed:
            print("  ✅ Test 1 PASSE\n")
            return True
        else:
            print("  ❌ Test 1 ECHOUE\n")
            return False
    except Exception as e:
        print(f"  ❌ Erreur: {e}\n")
        return False


def test_2_celery_has_completion_check():
    """Test 2: execute_workflow verifie si completed avant execution."""
    print("\n[Test 2] Verification check completion dans execute_workflow...")
    
    try:
        from services.celery_app import execute_workflow
        source = inspect.getsource(execute_workflow)
        
        checks = [
            ("check_if_completed_sync", "Fonction de verification"),
            ("internal_status", "Check du statut"),
            ("completed", "Check completed"),
            ("task_runs_count", "Check nombre de runs"),
            ("completed pour", "Message d'abandon"),
            ("acks_late=True", "Configuration acks_late"),
            ("reject_on_worker_lost=True", "Configuration reject_on_worker_lost")
        ]
        
        all_passed = True
        for check_str, description in checks:
            if check_str in source:
                print(f"  ✅ {description}: trouve")
            else:
                print(f"  ❌ {description}: MANQUANT")
                all_passed = False
        
        if all_passed:
            print("  ✅ Test 2 PASSE\n")
            return True
        else:
            print("  ❌ Test 2 ECHOUE\n")
            return False
    except Exception as e:
        print(f"  ❌ Erreur: {e}\n")
        return False


def test_3_database_checks_status_before_insert():
    """Test 3: start_task_run verifie le statut AVANT l'insertion."""
    print("\n[Test 3] Verification ordre check/insert dans start_task_run...")
    
    try:
        from services.database_persistence_service import DatabasePersistenceService
        source = inspect.getsource(DatabasePersistenceService.start_task_run)
        
        # Verifier que le check est avant l'insert
        status_check_pos = source.find("current_status = await conn.fetchval")
        insert_pos = source.find("INSERT INTO task_runs")
        error_check_pos = source.find("Invalid status transition")
        
        checks_passed = True
        
        if status_check_pos > 0:
            print(f"  ✅ Verification du statut: trouvee (pos {status_check_pos})")
        else:
            print("  ❌ Verification du statut: MANQUANTE")
            checks_passed = False
        
        if insert_pos > 0:
            print(f"  ✅ Insertion task_run: trouvee (pos {insert_pos})")
        else:
            print("  ❌ Insertion task_run: MANQUANTE")
            checks_passed = False
        
        if error_check_pos > 0:
            print(f"  ✅ Check erreur transition: trouve (pos {error_check_pos})")
        else:
            print("  ❌ Check erreur transition: MANQUANT")
            checks_passed = False
        
        if status_check_pos > 0 and insert_pos > 0:
            if status_check_pos < insert_pos:
                print("  ✅ ORDRE CORRECT: Check AVANT insert")
            else:
                print("  ❌ ORDRE INCORRECT: Insert avant check (race condition!)")
                checks_passed = False
        
        # Verifier les commentaires de correction
        if "CORRECTION" in source and "Verifier le statut AVANT" in source:
            print("  ✅ Commentaire de correction: present")
        else:
            print("  ⚠️  Commentaire de correction: manquant (mais code ok)")
        
        if checks_passed:
            print("  ✅ Test 3 PASSE\n")
            return True
        else:
            print("  ❌ Test 3 ECHOUE\n")
            return False
    except Exception as e:
        print(f"  ❌ Erreur: {e}\n")
        return False


def test_4_quality_score_in_correct_location():
    """Test 4: Le score de qualite est cherche dans quality_assurance."""
    print("\n[Test 4] Verification location du score de qualite...")
    
    try:
        from graph.workflow_graph import _should_merge_or_debug_after_monday_validation
        source = inspect.getsource(_should_merge_or_debug_after_monday_validation)
        
        checks = [
            ('results.get("quality_assurance")', "Acces quality_assurance"),
            ("overall_score", "Extraction du score"),
            ("< 30", "Seuil permissif (30)"),
            ("CORRECTION", "Commentaire de correction"),
        ]
        
        all_passed = True
        for check_str, description in checks:
            if check_str in source:
                print(f"  ✅ {description}: trouve")
            else:
                print(f"  ⚠️  {description}: non trouve")
                # Ne pas échouer pour les commentaires
                if "CORRECTION" not in description:
                    all_passed = False
        
        # Verifier qu'on ne cherche plus dans qa_results comme location principale
        if 'qa_results = results.get("quality_assurance")' not in source:
            print("  ✅ Pas de confusion qa_results/quality_assurance")
        else:
            print("  ❌ Confusion qa_results/quality_assurance")
            all_passed = False
        
        if all_passed:
            print("  ✅ Test 4 PASSE\n")
            return True
        else:
            print("  ❌ Test 4 ECHOUE\n")
            return False
    except Exception as e:
        print(f"  ❌ Erreur: {e}\n")
        return False


def test_5_qa_node_stores_in_quality_assurance():
    """Test 5: Le noeud QA stocke bien dans quality_assurance."""
    print("\n[Test 5] Verification stockage QA dans quality_assurance...")
    
    try:
        from nodes.qa_node import quality_assurance_automation
        source = inspect.getsource(quality_assurance_automation)
        
        checks = [
            ('state["results"]["quality_assurance"]', "Cle quality_assurance"),
            ('"overall_score": qa_summary["overall_score"]', "Stockage overall_score"),
            ('"quality_gate_passed"', "Stockage quality_gate_passed"),
        ]
        
        all_passed = True
        for check_str, description in checks:
            if check_str in source:
                print(f"  ✅ {description}: trouve")
            else:
                print(f"  ❌ {description}: MANQUANT")
                all_passed = False
        
        if all_passed:
            print("  ✅ Test 5 PASSE\n")
            return True
        else:
            print("  ❌ Test 5 ECHOUE\n")
            return False
    except Exception as e:
        print(f"  ❌ Erreur: {e}\n")
        return False


def test_6_event_loop_management():
    """Test 6: Gestion correcte des event loops dans Celery."""
    print("\n[Test 6] Verification gestion event loop...")
    
    try:
        from services.celery_app import execute_workflow
        source = inspect.getsource(execute_workflow)
        
        checks = [
            ("asyncio.new_event_loop()", "Creation nouvelle loop"),
            ("asyncio.set_event_loop(loop)", "Definition de la loop"),
            ("loop.close()", "Fermeture de la loop"),
            ("loop.run_until_complete", "Execution dans la loop"),
        ]
        
        all_passed = True
        for check_str, description in checks:
            if check_str in source:
                print(f"  ✅ {description}: trouve")
            else:
                print(f"  ❌ {description}: MANQUANT")
                all_passed = False
        
        if all_passed:
            print("  ✅ Test 6 PASSE\n")
            return True
        else:
            print("  ❌ Test 6 ECHOUE\n")
            return False
    except Exception as e:
        print(f"  ❌ Erreur: {e}\n")
        return False


def run_all_tests():
    """Execute tous les tests et affiche un resume."""
    print("\n" + "="*70)
    print("🧪 TESTS DE STRUCTURE DU CODE - CORRECTIONS SIGSEGV")
    print("="*70)
    
    tests = [
        ("Nettoyage LangSmith", test_1_finalize_node_has_langsmith_cleanup),
        ("Check completion avant execution", test_2_celery_has_completion_check),
        ("Ordre check/insert (race condition)", test_3_database_checks_status_before_insert),
        ("Location score qualite", test_4_quality_score_in_correct_location),
        ("Stockage QA results", test_5_qa_node_stores_in_quality_assurance),
        ("Gestion event loop", test_6_event_loop_management),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"❌ Erreur lors du test '{test_name}': {e}\n")
            results.append((test_name, False))
    
    # Resume final
    print("\n" + "="*70)
    print("📋 RESUME DES TESTS")
    print("="*70 + "\n")
    
    for test_name, passed in results:
        status = "✅ PASSE" if passed else "❌ ECHOUE"
        print(f"  {test_name:.<55} {status}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print("\n" + "="*70)
    if passed_count == total_count:
        print(f"🎉 TOUS LES TESTS PASSES ({passed_count}/{total_count})")
        print("="*70 + "\n")
        return 0
    else:
        print(f"⚠️  CERTAINS TESTS ONT ECHOUE ({passed_count}/{total_count})")
        print("="*70 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())

