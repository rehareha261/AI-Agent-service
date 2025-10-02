#!/usr/bin/env python3
"""
Script de test pour vérifier les corrections apportées au système AI-Agent.

Ce script teste :
1. La correction de la sérialisation JSON dans database_persistence_service
2. La récupération du répertoire de travail dans les nœuds
3. La création de PR après validation humaine
4. La configuration de logging Celery
"""

import asyncio
import json
import os
import tempfile
import logging
from unittest.mock import Mock, patch
from typing import Dict, Any

# Import des modules à tester
from services.database_persistence_service import DatabasePersistenceService
from utils.helpers import get_working_directory, validate_working_directory, ensure_working_directory
from services.pull_request_service import pr_service
from services.logging_service import logging_service
from models.state import GraphState
from models.schemas import TaskRequest, TaskPriority, TaskType


def test_json_serialization():
    """Test la correction de la sérialisation JSON."""
    print("🧪 Test 1: Sérialisation JSON corrigée")
    
    persistence = DatabasePersistenceService()
    
    # Test avec un dictionnaire normal
    normal_dict = {"test": "value", "number": 42}
    cleaned = persistence._clean_for_json_serialization(normal_dict)
    print(f"  ✅ Dict normal: {cleaned}")
    
    # Test avec un objet complexe
    class ComplexObject:
        def __init__(self):
            self.attribute = "value"
            self.nested = {"inner": "data"}
    
    complex_obj = ComplexObject()
    cleaned_complex = persistence._clean_for_json_serialization(complex_obj)
    print(f"  ✅ Objet complexe: {cleaned_complex}")
    
    # Test de sérialisation JSON complète
    try:
        json_str = json.dumps(cleaned_complex)
        print(f"  ✅ Sérialisation JSON réussie: {len(json_str)} caractères")
    except Exception as e:
        print(f"  ❌ Erreur sérialisation: {e}")
        return False
    
    print("  ✅ Test sérialisation JSON: RÉUSSI\n")
    return True


def test_working_directory_recovery():
    """Test la récupération du répertoire de travail."""
    print("🧪 Test 2: Récupération du répertoire de travail")
    
    # Créer un répertoire temporaire pour les tests
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"  📁 Répertoire temporaire créé: {temp_dir}")
        
        # Test 1: État avec working_directory au niveau racine
        state1 = {
            "working_directory": temp_dir,
            "results": {}
        }
        
        wd1 = get_working_directory(state1)
        print(f"  ✅ Récupération niveau racine: {wd1}")
        assert wd1 == temp_dir, f"Expected {temp_dir}, got {wd1}"
        
        # Test 2: État avec working_directory dans results
        state2 = {
            "results": {
                "working_directory": temp_dir,
                "prepare_result": {"working_directory": temp_dir}
            }
        }
        
        wd2 = get_working_directory(state2)
        print(f"  ✅ Récupération depuis results: {wd2}")
        assert wd2 == temp_dir, f"Expected {temp_dir}, got {wd2}"
        
        # Test 3: Validation du répertoire
        is_valid = validate_working_directory(temp_dir, "test_node")
        print(f"  ✅ Validation répertoire: {is_valid}")
        assert is_valid, "Le répertoire temporaire devrait être valide"
        
        # Test 4: ensure_working_directory avec récupération
        state3 = {
            "results": {
                "prepare_result": {"working_directory": temp_dir}
            }
        }
        
        ensured_wd = ensure_working_directory(state3, "test_")
        print(f"  ✅ Répertoire assuré: {ensured_wd}")
        assert os.path.exists(ensured_wd), "Le répertoire assuré devrait exister"
    
    print("  ✅ Test récupération répertoire de travail: RÉUSSI\n")
    return True


async def test_pr_creation():
    """Test la création de PR après validation."""
    print("🧪 Test 3: Création de PR après validation")
    
    # Mock des outils GitHub
    with patch('nodes.merge_node.GitHubTool') as mock_github_tool:
        # Configurer le mock pour retourner un succès
        mock_instance = Mock()
        # Le mock doit retourner une coroutine
        async def mock_arun(*args, **kwargs):
            return {
                "success": True,
                "pr_number": 123,
                "pr_url": "https://github.com/test/repo/pull/123"
            }
        mock_instance._arun = mock_arun
        mock_github_tool.return_value = mock_instance
        
        # Créer un état de test
        task_request = TaskRequest(
            task_id="test_task",
            title="Test PR Creation",
            description="Test description for PR creation",
            priority=TaskPriority.MEDIUM,
            task_type=TaskType.FEATURE,
            repository_url="https://github.com/test/repo"
        )
        
        # Créer un répertoire temporaire réel pour le test
        with tempfile.TemporaryDirectory() as temp_dir:
            state = GraphState(
                task=task_request,
                results={
                    "working_directory": temp_dir,
                    "git_result": {
                        "branch_name": "feature/test-branch"
                    },
                    "modified_files": ["test_file.py"],
                    "test_results": [{"success": True}],
                    "qa_results": {"overall_score": 85}
                }
            )
            
            # Tester la création de PR
            result = await pr_service.ensure_pull_request_created(state)
            
            print(f"  ✅ Résultat création PR: {result}")
            assert result.success, f"La création de PR devrait réussir: {result.error}"
            assert result.pr_info.number == 123, "Le numéro de PR devrait être 123"
            
            # Vérifier les propriétés du PR créé
            assert result.pr_info.number == 123, "Le numéro de PR devrait être 123"
            assert result.pr_info.url == "https://github.com/test/repo/pull/123", "L'URL devrait être correcte"
            assert result.pr_info.branch == "feature/test-branch", "La branche devrait être correcte"
        
    print("  ✅ Test création PR: RÉUSSI\n")
    return True


def test_celery_logging_config():
    """Test la configuration du logging Celery."""
    print("🧪 Test 4: Configuration du logging Celery")
    
    # Créer un répertoire temporaire pour les logs
    with tempfile.TemporaryDirectory() as temp_dir:
        # Changer temporairement le répertoire de travail
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            # Tester la configuration du logging
            logging_service.setup_logging()
            
            # Vérifier que le répertoire logs a été créé
            logs_info = logging_service.get_logs_info()
            logs_dir = logs_info['logs_directory']
            assert os.path.exists(logs_dir), "Le répertoire logs devrait être créé"
            print(f"  ✅ Répertoire logs créé: {logs_dir}")
            
            # Vérifier que des handlers ont été créés
            assert logs_info['handlers_count'] > 0, "Des handlers devraient être créés"
            print(f"  ✅ Handlers créés: {logs_info['handlers']}")
            
            # ✅ NOUVEAU: Vérifier le fichier logs.txt principal
            main_log_file = logs_info['main_log_file']
            assert main_log_file is not None, "Le fichier logs.txt devrait être configuré"
            print(f"  ✅ Fichier logs.txt configuré: {main_log_file}")
            
            # Tester qu'un logger existe et fonctionne
            logger = logging.getLogger('ai_agent_background')
            logger.info("Test message for logs.txt file")
            assert len(logger.handlers) > 0, "Le logger devrait avoir des handlers"
            print(f"  ✅ Logger configuré avec {len(logger.handlers)} handlers")
            
            # Vérifier que le fichier logs.txt a été créé
            if os.path.exists(main_log_file):
                file_size = os.path.getsize(main_log_file)
                print(f"  ✅ Fichier logs.txt créé: {file_size} bytes")
                
                # Vérifier le contenu
                with open(main_log_file, 'r') as f:
                    content = f.read()
                    if "Test message for logs.txt file" in content:
                        print(f"  ✅ Message de test trouvé dans logs.txt")
                    else:
                        print(f"  ⚠️ Message de test non trouvé dans logs.txt")
            else:
                print(f"  ⚠️ Fichier logs.txt non créé encore")
            
            # Vérifier le fichier de métadonnées
            metadata_file = os.path.join(logs_dir, "session_metadata.json")
            if os.path.exists(metadata_file):
                print(f"  ✅ Métadonnées session créées: {metadata_file}")
            else:
                print(f"  ⚠️ Métadonnées session non créées (peut être normal)")
            print(f"  ✅ Configuration logging: OK")
            
        finally:
            os.chdir(original_cwd)
    
    print("  ✅ Test configuration logging Celery: RÉUSSI\n")
    return True


def test_error_handling():
    """Test la gestion d'erreurs améliorée."""
    print("🧪 Test 5: Gestion d'erreurs améliorée")
    
    # Test 1: Validation de répertoire inexistant
    fake_dir = "/path/that/does/not/exist"
    is_valid = validate_working_directory(fake_dir, "test_node")
    assert not is_valid, "Un répertoire inexistant ne devrait pas être valide"
    print(f"  ✅ Validation répertoire inexistant: {not is_valid}")
    
    # Test 2: get_working_directory avec état vide
    empty_state = {}
    wd_empty = get_working_directory(empty_state)
    assert wd_empty is None, "État vide devrait retourner None"
    print(f"  ✅ État vide: {wd_empty is None}")
    
    # Test 3: Sérialisation d'objet non-sérialisable
    persistence = DatabasePersistenceService()
    
    class NonSerializable:
        def __init__(self):
            self.func = lambda x: x  # Les fonctions ne sont pas sérialisables
    
    non_ser = NonSerializable()
    cleaned = persistence._clean_for_json_serialization(non_ser)
    print(f"  ✅ Objet non-sérialisable nettoyé: {type(cleaned)}")
    
    # Le résultat devrait être un dict avec les attributs convertis
    assert isinstance(cleaned, dict), "Le résultat devrait être un dict"
    
    print("  ✅ Test gestion d'erreurs: RÉUSSI\n")
    return True


async def main():
    """Fonction principale qui lance tous les tests."""
    print("🧪 DÉMARRAGE DES TESTS DE CORRECTION AI-AGENT")
    print("=" * 60)
    
    tests = [
        ("Sérialisation JSON", test_json_serialization),
        ("Récupération répertoire de travail", test_working_directory_recovery),
        ("Création PR", test_pr_creation),
        ("Configuration logging Celery", test_celery_logging_config),
        ("Gestion d'erreurs", test_error_handling),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ❌ Erreur dans {test_name}: {e}")
            results.append((test_name, False))
    
    # Résumé des résultats
    print("=" * 60)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ RÉUSSI" if result else "❌ ÉCHOUÉ"
        print(f"{test_name:.<50} {status}")
        if result:
            passed += 1
    
    print("=" * 60)
    print(f"🎯 RÉSULTAT GLOBAL: {passed}/{total} tests réussis")
    
    if passed == total:
        print("🎉 TOUS LES TESTS SONT RÉUSSIS ! Les corrections sont fonctionnelles.")
        return True
    else:
        print("⚠️ Certains tests ont échoué. Vérifiez les corrections.")
        return False


if __name__ == "__main__":
    import sys
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 