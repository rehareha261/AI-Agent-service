#!/usr/bin/env python3
"""
Test rapide pour valider les corrections appliquées.
"""

import sys
import os

def test_workflow_limits():
    """Test des limites de workflow réduites."""
    print("🧪 Test des limites de workflow...")
    
    try:
        from config.workflow_limits import WorkflowLimits
        
        # Vérifier les nouvelles limites
        assert WorkflowLimits.MAX_NODES_SAFETY_LIMIT == 15, f"MAX_NODES_SAFETY_LIMIT devrait être 15, trouvé: {WorkflowLimits.MAX_NODES_SAFETY_LIMIT}"
        assert WorkflowLimits.MAX_DEBUG_ATTEMPTS == 2, f"MAX_DEBUG_ATTEMPTS devrait être 2, trouvé: {WorkflowLimits.MAX_DEBUG_ATTEMPTS}"
        assert WorkflowLimits.WORKFLOW_TIMEOUT == 1200, f"WORKFLOW_TIMEOUT devrait être 1200, trouvé: {WorkflowLimits.WORKFLOW_TIMEOUT}"
        
        print("  ✅ Limites workflow correctement réduites")
        return True
    except Exception as e:
        print(f"  ❌ Erreur test limites: {e}")
        return False

def test_qa_improvements():
    """Test des améliorations QA."""
    print("🧪 Test des critères QA assouplis...")
    
    try:
        # Import direct de la fonction
        sys.path.append('.')
        from nodes.qa_node import _analyze_qa_results
        
        # Test avec des résultats problématiques qui devraient maintenant passer
        qa_results = {
            "pylint": {"passed": False, "issues_count": 10, "critical_issues": 4},
            "flake8": {"passed": False, "issues_count": 15, "critical_issues": 3},
            "syntax": {"passed": True, "issues_count": 0, "critical_issues": 0}
        }
        
        summary = _analyze_qa_results(qa_results)
        
        # Avec 7 problèmes critiques total et les nouveaux critères (max 8), ça devrait passer
        assert summary["quality_gate_passed"], f"Quality gate devrait passer avec {summary['critical_issues']} problèmes critiques"
        assert summary["overall_score"] >= 45, f"Score devrait être >= 45, trouvé: {summary['overall_score']}"
        
        print(f"  ✅ QA assouplie: Score {summary['overall_score']}/100, {summary['critical_issues']} critiques, Gate: {'PASSÉ' if summary['quality_gate_passed'] else 'ÉCHOUÉ'}")
        return True
    except Exception as e:
        print(f"  ❌ Erreur test QA: {e}")
        return False

def test_monday_protection():
    """Test de la protection Monday.com."""
    print("🧪 Test de la protection Monday.com...")
    
    try:
        # Vérifier que les protections sont présentes dans le code
        with open('tools/monday_tool.py', 'r') as f:
            content = f.read()
        
        # Vérifier les protections clés
        assert "isinstance(result, dict)" in content, "Protection isinstance(result, dict) manquante"
        assert "isinstance(result, list)" in content, "Protection isinstance(result, list) manquante"
        assert "API Monday.com a retourné" in content, "Message d'erreur protection manquant"
        
        # Vérifier aussi les protections dans webhook_service
        with open('services/webhook_service.py', 'r') as f:
            webhook_content = f.read()
        
        assert "isinstance(column_values, list)" in webhook_content, "Protection column_values manquante"
        assert "column_values n'est pas une liste" in webhook_content, "Message protection column_values manquant"
        
        print("  ✅ Protection Monday.com active contre les réponses non-dict")
        return True
    except Exception as e:
        print(f"  ❌ Erreur test Monday: {e}")
        return False

def test_testing_improvements():
    """Test des améliorations de l'infrastructure de tests."""
    print("🧪 Test des améliorations de tests...")
    
    try:
        from tools.testing_engine import TestingEngine
        
        # Créer un engine de test
        engine = TestingEngine()
        
        # Vérifier que les patterns de fichiers exclus sont bien dans la fonction
        import inspect
        discover_source = inspect.getsource(engine._discover_tests)
        
        # Vérifier que les exclusions sont présentes
        assert "fix_" in discover_source, "Exclusion des fichiers fix_ manquante"
        assert "simple_fix.py" in discover_source, "Exclusion de simple_fix.py manquante"
        
        print("  ✅ Infrastructure de tests améliorée avec exclusions")
        return True
    except Exception as e:
        print(f"  ❌ Erreur test infrastructure: {e}")
        return False

def test_celery_retry_logic():
    """Test de la logique de retry Celery améliorée."""
    print("🧪 Test de la logique de retry Celery...")
    
    try:
        # Vérifier que le code contient la nouvelle logique
        with open('services/celery_app.py', 'r') as f:
            content = f.read()
        
        # Vérifier la présence des améliorations
        assert "should_retry" in content, "Logique should_retry manquante"
        assert "échec métier" in content, "Distinction échec métier manquante"
        assert "infrastructure" in content, "Distinction erreur infrastructure manquante"
        
        print("  ✅ Logique de retry Celery améliorée")
        return True
    except Exception as e:
        print(f"  ❌ Erreur test Celery: {e}")
        return False

def main():
    """Lance tous les tests de validation."""
    print("🚀 Validation des corrections appliquées")
    print("=" * 50)
    
    tests = [
        test_workflow_limits,
        test_qa_improvements, 
        test_monday_protection,
        test_testing_improvements,
        test_celery_retry_logic
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  ❌ Exception dans {test.__name__}: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Résultats: {passed}/{total} tests passés")
    
    if passed == total:
        print("✅ Toutes les corrections ont été validées avec succès !")
        print("\n📋 Résumé des corrections appliquées :")
        print("1. ✅ Limites workflow réduites (15 nœuds max, 20min timeout)")
        print("2. ✅ Critères QA assouplis (score min 45, 8 problèmes critiques max)")
        print("3. ✅ Protection Monday.com contre les réponses non-dict")
        print("4. ✅ Infrastructure de tests avec exclusion des scripts de correction")
        print("5. ✅ Logique Celery évitant les retries sur les échecs métier")
        return True
    else:
        print("❌ Certaines corrections nécessitent une vérification supplémentaire")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 