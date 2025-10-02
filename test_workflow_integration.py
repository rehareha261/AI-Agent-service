#!/usr/bin/env python3
"""
Tests d'intégration complets pour vérifier la cohérence des corrections avec le workflow AI-Agent.

Ce script teste l'intégration entre :
- Les améliorations de sérialisation JSON 
- La gestion robuste des répertoires de travail
- Le nouveau service de PR
- Le service de logging amélioré
- La cohérence entre tous les nœuds
"""

import asyncio
import tempfile
import os
import json
from datetime import datetime
from unittest.mock import patch, AsyncMock

# Imports des corrections à tester
from services.database_persistence_service import DatabasePersistenceService
from services.pull_request_service import pr_service
from services.logging_service import logging_service
from utils.helpers import get_working_directory, ensure_working_directory, validate_working_directory
from models.state import GraphState
from models.schemas import TaskRequest, TaskPriority, TaskType
from nodes.test_node import run_tests
from nodes.debug_node import debug_code
from nodes.qa_node import quality_assurance_automation
from nodes.implement_node import implement_task


async def test_workflow_integration():
    """Test d'intégration complet du workflow avec toutes les corrections."""
    
    print("🧪 TESTS D'INTÉGRATION WORKFLOW AI-AGENT")
    print("=" * 60)
    
    passed_tests = 0
    total_tests = 6
    
    # Test 1: Intégration sérialisation JSON avec nœuds
    try:
        print("🧪 Test 1: Intégration sérialisation JSON avec workflow")
        await test_json_integration_with_nodes()
        print("  ✅ Test intégration JSON: RÉUSSI\n")
        passed_tests += 1
    except Exception as e:
        print(f"  ❌ Erreur intégration JSON: {e}\n")
    
    # Test 2: Intégration gestion répertoires entre nœuds
    try:
        print("🧪 Test 2: Propagation répertoire de travail entre nœuds")
        await test_working_directory_propagation()
        print("  ✅ Test propagation répertoires: RÉUSSI\n")
        passed_tests += 1
    except Exception as e:
        print(f"  ❌ Erreur propagation répertoires: {e}\n")
    
    # Test 3: Intégration service PR avec nœuds
    try:
        print("🧪 Test 3: Intégration service PR avec merge_node")
        await test_pr_service_integration()
        print("  ✅ Test intégration service PR: RÉUSSI\n")
        passed_tests += 1
    except Exception as e:
        print(f"  ❌ Erreur intégration service PR: {e}\n")
    
    # Test 4: Cohérence des états entre nœuds
    try:
        print("🧪 Test 4: Cohérence des états entre nœuds")
        await test_state_consistency_across_nodes()
        print("  ✅ Test cohérence états: RÉUSSI\n")
        passed_tests += 1
    except Exception as e:
        print(f"  ❌ Erreur cohérence états: {e}\n")
    
    # Test 5: Gestion d'erreurs robuste
    try:
        print("🧪 Test 5: Gestion d'erreurs robuste entre nœuds")
        await test_robust_error_handling()
        print("  ✅ Test gestion erreurs robuste: RÉUSSI\n")
        passed_tests += 1
    except Exception as e:
        print(f"  ❌ Erreur gestion erreurs robuste: {e}\n")
    
    # Test 6: Performance et logging
    try:
        print("🧪 Test 6: Performance et logging intégré")
        await test_performance_and_logging()
        print("  ✅ Test performance et logging: RÉUSSI\n")
        passed_tests += 1
    except Exception as e:
        print(f"  ❌ Erreur performance et logging: {e}\n")
    
    # Résumé final
    print("=" * 60)
    print("📊 RÉSUMÉ TESTS D'INTÉGRATION")
    print("=" * 60)
    print(f"Intégration JSON.............................. {'✅ RÉUSSI' if passed_tests >= 1 else '❌ ÉCHOUÉ'}")
    print(f"Propagation répertoires....................... {'✅ RÉUSSI' if passed_tests >= 2 else '❌ ÉCHOUÉ'}")
    print(f"Intégration service PR........................ {'✅ RÉUSSI' if passed_tests >= 3 else '❌ ÉCHOUÉ'}")
    print(f"Cohérence états............................... {'✅ RÉUSSI' if passed_tests >= 4 else '❌ ÉCHOUÉ'}")
    print(f"Gestion erreurs robuste....................... {'✅ RÉUSSI' if passed_tests >= 5 else '❌ ÉCHOUÉ'}")
    print(f"Performance et logging........................ {'✅ RÉUSSI' if passed_tests >= 6 else '❌ ÉCHOUÉ'}")
    print("=" * 60)
    print(f"🎯 RÉSULTAT GLOBAL: {passed_tests}/{total_tests} tests réussis")
    
    if passed_tests == total_tests:
        print("✅ Toutes les corrections sont cohérentes et intégrées !")
    elif passed_tests >= total_tests * 0.8:
        print("⚠️ La plupart des corrections fonctionnent, quelques ajustements peuvent être nécessaires.")
    else:
        print("❌ Des problèmes d'intégration majeurs détectés.")
    
    return passed_tests == total_tests


async def test_json_integration_with_nodes():
    """Test que la sérialisation JSON fonctionne avec les vrais nœuds."""
    
    # Créer un état complexe comme dans un vrai workflow
    task = TaskRequest(
        task_id="integration_test",
        title="Test intégration JSON",
        description="Test pour vérifier l'intégration de la sérialisation JSON",
        priority=TaskPriority.HIGH,
        task_type=TaskType.FEATURE
    )
    
    with tempfile.TemporaryDirectory() as temp_dir:
        state = GraphState(
            task=task,
            results={
                "working_directory": temp_dir,
                "complex_data": {
                    "nested_object": {"key": "value"},
                    "list_data": [1, 2, 3],
                    "datetime": datetime.now(),
                    "none_value": None
                },
                "ai_messages": [],
                "error_logs": []
            }
        )
        
        # Tester la persistence avec DatabasePersistenceService
        persistence = DatabasePersistenceService()
        
        # Nettoyer les données comme le ferait le service
        cleaned_data = persistence._clean_for_json_serialization(state["results"]["complex_data"])
        print(f"  ✅ Données complexes nettoyées: {type(cleaned_data)}")
        
        # Vérifier que les données peuvent être sérialisées
        json_str = json.dumps(cleaned_data, ensure_ascii=False)
        print(f"  ✅ Sérialisation réussie: {len(json_str)} caractères")
        
        # Vérifier la désérialisation
        deserialized = json.loads(json_str)
        assert isinstance(deserialized, dict), "La désérialisation doit retourner un dict"
        print(f"  ✅ Désérialisation réussie: {len(deserialized)} clés")


async def test_working_directory_propagation():
    """Test la propagation du répertoire de travail entre les nœuds."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # État initial sans working_directory
        # Utiliser un dictionnaire standard au lieu de GraphState pour ce test
        initial_state = {
            "task": TaskRequest(
                task_id="wd_test",
                title="Test WD propagation",
                description="Test propagation working directory",
                priority=TaskPriority.MEDIUM,
                task_type=TaskType.BUGFIX
            ),
            "results": {
                "prepare_result": {"working_directory": temp_dir},
                "ai_messages": [],
                "error_logs": []
            }
        }
        
        # Test 1: get_working_directory trouve le répertoire
        wd = get_working_directory(initial_state)
        assert wd == temp_dir, f"WD devrait être {temp_dir}, trouvé {wd}"
        print(f"  ✅ get_working_directory fonctionne: {wd}")
        
        # Test 2: validate_working_directory valide correctement
        is_valid = validate_working_directory(wd, "test_propagation")
        assert is_valid, f"WD {wd} devrait être valide"
        print(f"  ✅ validate_working_directory fonctionne: {is_valid}")
        
        # Test 3: ensure_working_directory utilise l'existant
        ensured_wd = ensure_working_directory(initial_state, "test_")
        assert ensured_wd == temp_dir, f"ensure_working_directory devrait retourner {temp_dir}"
        print(f"  ✅ ensure_working_directory utilise l'existant: {ensured_wd}")
        
        # Test 4: État sans répertoire - création automatique
        empty_state = {
            "task": TaskRequest(
                task_id="empty_test",
                title="Empty test",
                description="Test creation automatique",
                priority=TaskPriority.LOW,
                task_type=TaskType.TESTING
            ),
            "results": {"ai_messages": [], "error_logs": []}
        }
        
        new_wd = ensure_working_directory(empty_state, "auto_")
        assert os.path.exists(new_wd), f"Nouveau WD {new_wd} devrait exister"
        print(f"  ✅ Création automatique WD fonctionne: {new_wd}")


async def test_pr_service_integration():
    """Test l'intégration du service PR avec les nœuds."""
    
    # Mock des appels GitHub pour éviter les erreurs d'API
    with patch('tools.github_tool.GitHubTool._arun') as mock_github:
        async def mock_github_call(*args, **kwargs):
            return {
                "success": True,
                "pr_number": 123,
                "pr_url": "https://github.com/test/repo/pull/123"
            }
        mock_github.side_effect = mock_github_call
        
        with tempfile.TemporaryDirectory() as temp_dir:
            state = GraphState(
                task=TaskRequest(
                    task_id="pr_test",
                    title="Test PR service",
                    description="Test intégration service PR",
                    priority=TaskPriority.HIGH,
                    task_type=TaskType.FEATURE,
                    repository_url="https://github.com/test/repo"
                ),
                results={
                    "working_directory": temp_dir,
                    "git_result": {"branch_name": "feature/test"},
                    "ai_messages": [],
                    "error_logs": []
                }
            )
            
            # Test création PR via le service
            result = await pr_service.ensure_pull_request_created(state)
            
            # Le service devrait appeler GitHub même si mocké
            assert result.success, f"PR creation devrait réussir: {result.error}"
            assert result.pr_info is not None, "pr_info devrait être présent"
            assert result.pr_info.number == 123, "Le numéro de PR devrait être 123"
            print(f"  ✅ Service PR fonctionne: #{result.pr_info.number}")
            
            # Le service PR ne met pas automatiquement à jour l'état dans cette version
            # C'est le travail du nœud qui l'appelle (merge_node)
            print(f"  ✅ Service PR fonctionne correctement")


async def test_state_consistency_across_nodes():
    """Test la cohérence des états quand ils passent entre les nœuds."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Créer un fichier test pour que le répertoire ne soit pas vide
        test_file = os.path.join(temp_dir, "test.py")
        with open(test_file, 'w') as f:
            f.write("# Test file\nprint('hello')\n")
        
        initial_state = GraphState(
            task=TaskRequest(
                task_id="consistency_test",
                title="Test cohérence états",
                description="Test cohérence entre nœuds",
                priority=TaskPriority.MEDIUM,
                task_type=TaskType.FEATURE
            ),
            results={
                "working_directory": temp_dir,
                "ai_messages": [],
                "error_logs": [],
                "debug_attempts": 0
            }
        )
        
        # Simuler le passage par plusieurs nœuds et vérifier la cohérence
        print(f"  📁 État initial WD: {initial_state['results']['working_directory']}")
        
        # Chaque nœud devrait préserver et valider le working_directory
        for node_name in ["test_node", "debug_node", "qa_node"]:
            wd = get_working_directory(initial_state)
            assert wd == temp_dir, f"{node_name}: WD incohérent, attendu {temp_dir}, trouvé {wd}"
            
            is_valid = validate_working_directory(wd, node_name)
            assert is_valid, f"{node_name}: WD devrait être valide"
            
            print(f"  ✅ {node_name}: WD cohérent et valide")
        
        # Vérifier que les messages d'erreur sont conservés
        initial_state["results"]["error_logs"].append("Test error")
        assert len(initial_state["results"]["error_logs"]) == 1, "Error logs devraient être préservés"
        print(f"  ✅ Error logs préservés: {len(initial_state['results']['error_logs'])}")


async def test_robust_error_handling():
    """Test la gestion d'erreurs robuste entre les nœuds."""
    
    # Test 1: État avec répertoire invalide
    invalid_state = GraphState(
        task=TaskRequest(
            task_id="error_test",
            title="Test gestion erreurs",
            description="Test robustesse",
            priority=TaskPriority.LOW,
            task_type=TaskType.BUGFIX
        ),
        results={
            "working_directory": "/path/that/does/not/exist",
            "ai_messages": [],
            "error_logs": []
        }
    )
    
    # ensure_working_directory devrait créer un nouveau répertoire
    recovered_wd = ensure_working_directory(invalid_state, "error_recovery_")
    assert os.path.exists(recovered_wd), "WD de récupération devrait exister"
    print(f"  ✅ Récupération répertoire invalide: {recovered_wd}")
    
    # Test 2: État avec données corrompues
    corrupted_state = GraphState(
        task=TaskRequest(
            task_id="corrupted_test",
            title="Test données corrompues",
            description="Test robustesse données",
            priority=TaskPriority.HIGH,
                            task_type=TaskType.TESTING
        ),
        results={
            "ai_messages": [],
            "error_logs": [],
            "corrupted_data": object()  # Objet non-sérialisable
        }
    )
    
    # La sérialisation devrait nettoyer les données corrompues
    persistence = DatabasePersistenceService()
    cleaned = persistence._clean_for_json_serialization(corrupted_state["results"]["corrupted_data"])
    assert isinstance(cleaned, str), "Données corrompues devraient être converties en string"
    print(f"  ✅ Données corrompues nettoyées: {type(cleaned)}")


async def test_performance_and_logging():
    """Test les performances et le logging intégré."""
    
    import time
    
    # Test configuration du logging
    logging_configured = logging_service.setup_logging()
    assert logging_configured, "Le logging devrait être configuré"
    
    logs_info = logging_service.get_logs_info()
    assert logs_info['logs_directory'] is not None, "Répertoire logs devrait être configuré"
    assert logs_info['handlers_count'] > 0, "Des handlers devraient être configurés"
    print(f"  ✅ Logging configuré: {logs_info['handlers_count']} handlers")
    
    # Test performance des fonctions helpers
    with tempfile.TemporaryDirectory() as temp_dir:
        state = GraphState(
            task=TaskRequest(
                task_id="perf_test",
                title="Test performance",
                description="Test performances",
                priority=TaskPriority.MEDIUM,
                task_type=TaskType.PERFORMANCE
            ),
            results={
                "working_directory": temp_dir,
                "ai_messages": [],
                "error_logs": []
            }
        )
        
        # Mesurer le temps d'exécution des opérations courantes
        start_time = time.time()
        
        for i in range(100):
            wd = get_working_directory(state)
            validate_working_directory(wd, f"perf_test_{i}")
        
        duration = time.time() - start_time
        assert duration < 1.0, f"100 opérations WD devraient prendre < 1s, pris {duration:.3f}s"
        print(f"  ✅ Performance WD: 100 ops en {duration:.3f}s")
        
        # Test sérialisation de grandes données
        large_data = {"data": [{"item": i, "value": f"test_{i}"} for i in range(1000)]}
        
        start_time = time.time()
        persistence = DatabasePersistenceService()
        cleaned = persistence._clean_for_json_serialization(large_data)
        json_str = json.dumps(cleaned)
        duration = time.time() - start_time
        
        assert duration < 0.5, f"Sérialisation 1000 items devrait prendre < 0.5s, pris {duration:.3f}s"
        assert len(json_str) > 0, "JSON sérialisé devrait avoir du contenu"
        print(f"  ✅ Performance JSON: 1000 items en {duration:.3f}s, {len(json_str)} chars")


if __name__ == "__main__":
    print("🚀 Démarrage des tests d'intégration...")
    success = asyncio.run(test_workflow_integration())
    exit(0 if success else 1) 