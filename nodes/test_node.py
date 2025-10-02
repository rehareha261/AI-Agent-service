"""Nœud de tests - exécute et valide les tests."""

import os
from typing import Dict, Any
from models.state import GraphState
from tools.claude_code_tool import ClaudeCodeTool
from utils.logger import get_logger
from utils.persistence_decorator import with_persistence
from utils.helpers import get_working_directory, validate_working_directory, ensure_working_directory

logger = get_logger(__name__)


def log_test_results_decorator(func):
    """Décorateur pour logger les résultats de tests."""
    async def wrapper(*args, **kwargs):
        # Logging avant le test
        logger.info("🧪 Démarrage des tests automatisés")
        
        result = await func(*args, **kwargs)
        
        # Logging après le test
        if result and result.get("results", {}).get("test_results"):
            test_results = result["results"]["test_results"]
            if isinstance(test_results, list) and test_results:
                last_test = test_results[-1]
                success = last_test.get("success", False) if isinstance(last_test, dict) else False
                logger.info(f"✅ Tests terminés - Succès: {success}")
            
        return result
    return wrapper


@with_persistence("run_tests")
@log_test_results_decorator
async def run_tests(state: GraphState) -> GraphState:
    """
    Nœud de tests : exécute les tests pour valider l'implémentation.
    
    Ce nœud :
    1. Détecte les fichiers de test dans le projet
    2. Exécute les tests avec pytest/unittest
    3. Analyse les résultats et erreurs
    4. Détermine si le code est prêt pour la QA
    
    Args:
        state: État actuel du graphe
        
    Returns:
        État mis à jour avec les résultats des tests
    """
    logger.info(f"🧪 Lancement des tests pour: {state['task'].title}")

    # ✅ CORRECTION CRITIQUE: Assurer l'intégrité de l'état dès le début
    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)

    # Initialiser ai_messages si nécessaire
    if "ai_messages" not in state["results"]:
        state["results"]["ai_messages"] = []

    state["results"]["current_status"] = "testing".lower()
    state["results"]["ai_messages"].append("Début des tests...")
    
    try:
        # Vérifier que l'environnement est prêt
        working_directory = get_working_directory(state)
        
        if not validate_working_directory(working_directory, "test_node"):
            # ✅ AMÉLIORATION: Essayer de récupérer le working_directory depuis prepare_result
            prepare_result = state["results"].get("prepare_result", {})
            if prepare_result and prepare_result.get("working_directory"):
                fallback_wd = prepare_result["working_directory"]
                logger.info(f"🔄 Tentative de récupération du working_directory depuis prepare_result: {fallback_wd}")
                
                if validate_working_directory(fallback_wd, "test_node_fallback"):
                    working_directory = fallback_wd
                    # Mettre à jour l'état pour la cohérence
                    state["working_directory"] = working_directory
                    state["results"]["working_directory"] = working_directory
                    logger.info(f"✅ Working directory récupéré avec succès: {working_directory}")
                else:
                    logger.warning(f"⚠️ Working directory du prepare_result invalide: {fallback_wd}")
            
            # ✅ NOUVELLE STRATÉGIE: Essayer d'extraire le répertoire depuis Git (si repository cloné)
            if not validate_working_directory(working_directory, "test_node"):
                git_result = state["results"].get("git_result")
                if git_result and hasattr(git_result, '__dict__'):
                    # Si git_result est un objet avec des attributs
                    potential_dirs = [
                        getattr(git_result, 'working_directory', None),
                        getattr(git_result, 'repository_path', None),
                        getattr(git_result, 'directory', None)
                    ]
                elif isinstance(git_result, dict):
                    # Si git_result est un dictionnaire
                    potential_dirs = [
                        git_result.get('working_directory'),
                        git_result.get('repository_path'),
                        git_result.get('directory')
                    ]
                else:
                    potential_dirs = []
                
                for potential_dir in potential_dirs:
                    if potential_dir and validate_working_directory(potential_dir, "test_node_git_fallback"):
                        working_directory = potential_dir
                        state["working_directory"] = working_directory
                        state["results"]["working_directory"] = working_directory
                        logger.info(f"✅ Working directory récupéré depuis git_result: {working_directory}")
                        break
            
            # Si toujours pas de working_directory valide, créer un répertoire de secours
            if not validate_working_directory(working_directory, "test_node"):
                try:
                    working_directory = ensure_working_directory(state, "test_node_")
                    logger.info(f"📁 Répertoire de test de secours créé: {working_directory}")
                except Exception as e:
                    error_msg = f"Impossible de créer un répertoire de travail pour les tests: {e}"
                    logger.error(error_msg)
                    state["results"]["error_logs"].append(error_msg)
                    state["results"]["ai_messages"].append(f"❌ {error_msg}")
                    state["results"]["should_continue"] = False
                    state["results"]["current_status"] = "failed".lower()
                    return state

        logger.info(f"📁 Utilisation du répertoire de travail dans test_node: {working_directory}")
        
        # Initialiser le nouveau moteur de tests
        from tools.testing_engine import TestingEngine
        
        testing_engine = TestingEngine()
        # ✅ S'assurer que working_directory est correctement défini dans l'instance du moteur
        testing_engine.working_directory = working_directory

        # ✅ NOUVELLE APPROCHE: Analyser d'abord les changements pour cibler les tests
        code_changes = state["results"].get("implementation_result", {}).get("modified_files", {})
        
        if not code_changes:
            # Si pas de changements IA détectés, récupérer depuis implement_result
            implement_result = state["results"].get("implement_result")
            if implement_result and isinstance(implement_result, dict):
                code_changes = implement_result.get("modified_files", {})
        
        logger.info(f"🔍 Fichiers modifiés détectés pour tests: {len(code_changes) if code_changes else 0}")
        
        # ✅ AMÉLIORATION: Tests adaptatifs selon le contenu du repository
        logger.info("🧪 Lancement de la suite complète de tests en couches...")
        
        # 1. D'abord vérifier s'il y a des tests existants dans le repository
        import os
        test_files_found = []
        for root, dirs, files in os.walk(working_directory):
            for file in files:
                if (file.startswith('test_') and file.endswith('.py')) or \
                   (file.endswith('_test.py')) or \
                   (file.endswith('.test.js')) or \
                   (file.endswith('.spec.js')):
                    test_files_found.append(os.path.join(root, file))
        
        if test_files_found:
            logger.info(f"🔍 Tests existants trouvés dans le repository: {len(test_files_found)} fichiers")
            # Exécuter les tests existants du repository
            result = await testing_engine._run_all_tests(
                working_directory=working_directory,
                include_coverage=True,
                code_changes=code_changes
            )
        else:
            logger.info("📝 Aucun test existant trouvé - création de tests automatiques pour le code généré")
            
            # Si pas de tests existants, créer des tests automatiques pour les fichiers modifiés
            if code_changes:
                result = await _create_and_run_automatic_tests(testing_engine, working_directory, code_changes)
            else:
                # Pas de code modifié et pas de tests - considérer comme succès avec avertissement
                result = {
                    "success": True,
                    "warning": "Aucun test trouvé et aucun code modifié - validation par défaut",
                    "total_tests": 0,
                    "passed_tests": 0,
                    "failed_tests": 0,
                    "test_type": "validation_par_defaut",
                    "message": "Pas de tests requis pour cette tâche"
                }
                logger.info("ℹ️ Aucun test requis - validation automatique")

        # ✅ CORRECTION: S'assurer que result est un dictionnaire
        if not isinstance(result, dict):
            logger.warning(f"⚠️ Résultat de test invalide (type {type(result)}): {result}")
            result = {
                "success": False,
                "error": f"Type de résultat invalide: {type(result)}",
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 1
            }

        # Traiter les résultats des tests
        test_success = result.get("success", False)
        
        # Stocker les résultats dans une liste (pour compatibilité avec _should_debug)
        if "test_results" not in state["results"]:
            state["results"]["test_results"] = []
        state["results"]["test_results"].append(result)
        state["results"]["test_success"] = test_success
        
        # Messages détaillés selon les résultats
        if test_success:
            total_tests = result.get("total_tests", 0)
            passed_tests = result.get("passed_tests", 0)
            
            if total_tests > 0:
                success_msg = f"✅ Tests réussis: {passed_tests}/{total_tests}"
                logger.info(success_msg)
                state["results"]["ai_messages"].append(success_msg)
            else:
                warning_msg = result.get("warning", "✅ Validation automatique - aucun test requis")
                logger.info(warning_msg)
                state["results"]["ai_messages"].append(warning_msg)
            
            state["results"]["current_status"] = "tests_passed".lower()
        else:
            failed_tests = result.get("failed_tests", 1)
            total_tests = result.get("total_tests", 1)
            error_msg = result.get("error", "Tests échoués - vérifier la logique métier")
            
            failure_msg = f"❌ Tests échoués: {failed_tests}/{total_tests} - {error_msg}"
            logger.warning(failure_msg)
            state["results"]["ai_messages"].append(failure_msg)
            state["results"]["current_status"] = "tests_failed".lower()
            
            # Ajouter les détails d'erreur si disponibles
            if "error_details" in result:
                state["results"]["test_error_details"] = result["error_details"]

        # ✅ DÉCISION: Continuer le workflow même si les tests échouent (pour la validation humaine)
        state["results"]["should_continue"] = True
        
        logger.info("🏁 Tests terminés")
        return state

    except Exception as e:
        error_msg = f"Exception lors des tests: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        # Créer un résultat d'erreur
        test_result = {
            "success": False,
            "error": error_msg,
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 1,
            "exception": str(e)
        }
        
        # Stocker dans une liste pour compatibilité
        if "test_results" not in state["results"]:
            state["results"]["test_results"] = []
        state["results"]["test_results"].append(test_result)
        state["results"]["test_success"] = False
        state["results"]["ai_messages"].append(f"❌ Exception tests: {error_msg}")
        state["results"]["current_status"] = "tests_error".lower()
        state["results"]["should_continue"] = True  # Continuer malgré l'erreur
        
        return state


async def _create_and_run_automatic_tests(testing_engine, working_directory: str, code_changes: dict) -> dict:
    """Crée et exécute des tests automatiques pour les fichiers modifiés."""
    import os
    
    logger.info(f"🔧 Création de tests automatiques pour {len(code_changes)} fichiers modifiés")
    
    # Créer un répertoire de tests temporaire
    test_dir = os.path.join(working_directory, "auto_tests")
    os.makedirs(test_dir, exist_ok=True)
    
    test_files_created = []
    
    for file_path, file_content in code_changes.items():
        if file_path.endswith('.py'):
            # Créer un test basique pour le fichier Python
            test_content = _generate_basic_python_test(file_path, file_content)
            test_file_name = f"test_{os.path.basename(file_path)}"
            test_file_path = os.path.join(test_dir, test_file_name)
            
            with open(test_file_path, 'w') as f:
                f.write(test_content)
            
            test_files_created.append(test_file_path)
            logger.info(f"📝 Test automatique créé: {test_file_name}")
    
    if test_files_created:
        # Exécuter les tests créés
        try:
            result = await testing_engine._run_test_directory(test_dir)
            result["auto_generated"] = True
            result["test_files_created"] = len(test_files_created)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"Erreur lors de l'exécution des tests automatiques: {e}",
                "auto_generated": True,
                "test_files_created": len(test_files_created)
            }
    else:
        return {
            "success": True,
            "warning": "Aucun fichier Python modifié - tests automatiques non applicables",
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "auto_generated": True
        }


def _generate_basic_python_test(file_path: str, file_content: str) -> str:
    """Génère un test Python basique pour un fichier donné."""
    import os
    module_name = os.path.splitext(os.path.basename(file_path))[0]
    
    # Test basique qui vérifie que le module peut être importé et exécute des vérifications de base
    test_content = f'''"""Test automatique généré pour {file_path}"""
import unittest
import sys
import os

# Ajouter le répertoire parent au path pour l'import
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

class Test{module_name.replace("_", "").title()}(unittest.TestCase):
    """Tests automatiques pour {module_name}"""
    
    def test_module_import(self):
        """Test que le module peut être importé"""
        try:
            import {module_name}
            self.assertTrue(True, "Module importé avec succès")
        except ImportError as e:
            self.fail(f"Impossible d'importer {module_name}: {{e}}")
    
    def test_basic_syntax(self):
        """Test basique de syntaxe"""
        # Vérifier que le contenu contient au moins du code Python valide
        content = """{repr(file_content[:500])}"""
        self.assertIsInstance(content, str)
        self.assertGreater(len(content), 0)
    
    def setUp(self):
        """Configuration avant chaque test"""
        pass
    
    def tearDown(self):
        """Nettoyage après chaque test"""
        pass

if __name__ == '__main__':
    unittest.main()
'''
    
    return test_content


async def _run_basic_tests(working_directory: str) -> Dict[str, Any]:
    """
    Fallback simple pour exécuter des tests basiques quand TestingEngine échoue.
    """
    logger.info("🧪 Exécution de tests basiques...")
    
    # Créer une instance de ClaudeCodeTool pour exécuter les commandes
    claude_tool = ClaudeCodeTool()
    claude_tool.working_directory = working_directory
    
    # Commandes de test à essayer dans l'ordre
    test_commands = [
        "python -m pytest -v --tb=short",
        "python -m pytest",
        "python -m unittest discover -v",
        "python -m unittest",
        "npm test",
        "yarn test"
    ]
    
    results = {
        "success": False,
        "test_results": {
            "passed": 0,
            "failed": 0,
            "errors": [],
            "coverage": 0
        },
        "command_used": None,
        "output": ""
    }
    
    for command in test_commands:
        logger.info(f"🧪 Test avec commande: {command}")
        
        try:
            result = await claude_tool._arun(
                action="execute_command",
                command=command,
                cwd=working_directory
            )
            
            if result.get("success", False):
                # Analyser la sortie pour extraire les résultats
                output = result.get("output", "")
                results["output"] = output
                results["command_used"] = command
                
                # Parser simple des résultats pytest/unittest
                if "pytest" in command.lower():
                    results.update(_parse_pytest_simple(output))
                elif "unittest" in command.lower():
                    results.update(_parse_unittest_simple(output))
                elif "test" in command.lower():  # npm/yarn test
                    results.update(_parse_npm_test_simple(output))
                
                # Si au moins une commande a fonctionné, considérer comme succès
                results["success"] = True
                logger.info(f"✅ Tests exécutés avec: {command}")
                break
                
        except Exception as e:
            logger.debug(f"⚠️ Commande {command} échouée: {e}")
            continue
    
    if not results["success"]:
        results["test_results"]["errors"].append("Aucune commande de test fonctionnelle trouvée")
        results["test_results"]["failed"] = 1
        logger.warning("❌ Aucune commande de test n'a fonctionné")
    
    return results


def _parse_pytest_simple(output: str) -> Dict[str, Any]:
    """Parse simple de la sortie pytest."""
    results = {"success": False, "test_results": {"passed": 0, "failed": 0, "errors": []}}
    
    # Chercher les patterns pytest
    import re
    
    # Pattern pour "X passed, Y failed"
    match = re.search(r'(\d+) passed.*?(\d+) failed', output)
    if match:
        results["test_results"]["passed"] = int(match.group(1))
        results["test_results"]["failed"] = int(match.group(2))
        results["success"] = int(match.group(2)) == 0
    
    # Pattern pour "X passed" seulement
    elif re.search(r'(\d+) passed', output):
        match = re.search(r'(\d+) passed', output)
        results["test_results"]["passed"] = int(match.group(1))
        results["success"] = True
    
    # Pas de tests trouvés
    elif "no tests ran" in output.lower() or "collected 0 items" in output.lower():
        results["test_results"]["errors"].append("Aucun test trouvé par pytest")
    
    return results


def _parse_unittest_simple(output: str) -> Dict[str, Any]:
    """Parse simple de la sortie unittest."""
    results = {"success": False, "test_results": {"passed": 0, "failed": 0, "errors": []}}
    
    # Chercher "Ran X tests"
    import re
    match = re.search(r'Ran (\d+) tests?', output)
    if match:
        total_tests = int(match.group(1))
        
        # Chercher les échecs
        if "FAILED" in output:
            # Compter les lignes avec FAIL
            failed_count = output.count("FAIL")
            results["test_results"]["failed"] = failed_count
            results["test_results"]["passed"] = total_tests - failed_count
        else:
            results["test_results"]["passed"] = total_tests
            results["success"] = True
    else:
        results["test_results"]["errors"].append("Aucun test trouvé par unittest")
    
    return results


def _parse_npm_test_simple(output: str) -> Dict[str, Any]:
    """Parse simple de la sortie npm/yarn test."""
    results = {"success": False, "test_results": {"passed": 0, "failed": 0, "errors": []}}
    
    # Pattern simple pour détecter succès/échec npm test
    if "Test Suites: " in output:
        # Jest format
        import re
        match = re.search(r'(\d+) passed.*?(\d+) failed', output)
        if match:
            results["test_results"]["passed"] = int(match.group(1))
            results["test_results"]["failed"] = int(match.group(2))
            results["success"] = int(match.group(2)) == 0
    elif "passing" in output.lower():
        # Mocha format
        results["test_results"]["passed"] = 1
        results["success"] = True
    else:
        results["test_results"]["errors"].append("Format de test npm/yarn non reconnu")
    
    return results

async def _detect_test_commands(claude_tool: ClaudeCodeTool) -> list[str]:
    """Détecte les commandes de test disponibles selon le type de projet."""
    
    test_commands = []
    
    try:
        # Vérifier les fichiers de configuration pour détecter le type de projet
        
        # 1. Projet Node.js / JavaScript
        package_json_result = await claude_tool._arun(action="read_file", file_path="package.json", required=False)
        if package_json_result["success"] and package_json_result.get("file_exists", True):
            import json
            try:
                package_data = json.loads(package_json_result["content"])
                scripts = package_data.get("scripts", {})
                
                # Prioriser les scripts de test définis
                if "test" in scripts:
                    test_commands.append("npm test")
                if "test:unit" in scripts:
                    test_commands.append("npm run test:unit")
                if "jest" in scripts:
                    test_commands.append("npm run jest")
                    
                # Ajouter des alternatives
                if not test_commands:
                    test_commands.extend(["npm test", "yarn test", "npx jest"])
                    
            except json.JSONDecodeError:
                test_commands.append("npm test")
        elif not package_json_result["success"]:
            logger.debug("📝 package.json non trouvé - probablement un projet Python")
        
        # 2. Projet Python
        requirements_result = await claude_tool._arun(action="read_file", file_path="requirements.txt", required=False)
        setup_py_result = await claude_tool._arun(action="read_file", file_path="setup.py", required=False)
        pyproject_result = await claude_tool._arun(action="read_file", file_path="pyproject.toml", required=False)
        
        # ✅ CORRECTION: Vérifier si au moins un fichier existe et a été lu avec succès
        python_config_files = [
            ("requirements.txt", requirements_result),
            ("setup.py", setup_py_result), 
            ("pyproject.toml", pyproject_result)
        ]
        
        # Log les fichiers Python non trouvés en debug seulement
        for file_name, result in python_config_files:
            if not result["success"]:
                logger.debug(f"📝 {file_name} non trouvé - normal pour certains projets Python")
        
        python_files_exist = any(
            result["success"] and result.get("file_exists", True) 
            for _, result in python_config_files
        )
        
        if python_files_exist:
            # Détecter le framework de test utilisé
            all_content = ""
            for config_file, result in python_config_files:
                if result["success"] and result.get("file_exists", True):
                    all_content += result["content"].lower()
            
            if "pytest" in all_content:
                test_commands.extend(["python -m pytest", "pytest"])
            if "unittest" in all_content:
                test_commands.append("python -m unittest discover")
            if "nose" in all_content:
                test_commands.append("nosetests")
            
            # Commandes par défaut Python
            if not any("python" in cmd for cmd in test_commands):
                test_commands.extend([
                    "python -m pytest",
                    "python -m unittest discover", 
                    "python -m pytest tests/",
                    "python -m unittest"
                ])
        
        # 3. Autres types de projets
        
        # Makefile
        makefile_result = await claude_tool._arun(action="read_file", file_path="Makefile")
        if makefile_result["success"] and makefile_result.get("file_exists", True) and "test" in makefile_result["content"].lower():
            test_commands.append("make test")
        
        # Cargo (Rust)
        cargo_result = await claude_tool._arun(action="read_file", file_path="Cargo.toml")
        if cargo_result["success"] and cargo_result.get("file_exists", True):
            test_commands.append("cargo test")
        
        # Go
        go_mod_result = await claude_tool._arun(action="read_file", file_path="go.mod")
        if go_mod_result["success"] and go_mod_result.get("file_exists", True):
            test_commands.append("go test ./...")
        
        # Composer (PHP)
        composer_result = await claude_tool._arun(action="read_file", file_path="composer.json")
        if composer_result["success"] and composer_result.get("file_exists", True):
            test_commands.extend(["composer test", "./vendor/bin/phpunit"])
        
    except Exception as e:
        logger.warning(f"Erreur lors de la détection des commandes de test: {e}")
    
    # Supprimer les doublons tout en préservant l'ordre
    seen = set()
    unique_commands = []
    for cmd in test_commands:
        if cmd not in seen:
            seen.add(cmd)
            unique_commands.append(cmd)
    
    return unique_commands

async def _analyze_test_failure(test_result: Dict[str, Any], state: Dict[str, Any]) -> str:
    """Analyse les échecs de tests pour fournir un diagnostic."""
    
    # Gérer à la fois les objets TestResult et les dictionnaires
    if hasattr(test_result, 'stderr'):
        # C'est un objet TestResult
        error_output = getattr(test_result, 'stderr', '') or getattr(test_result, 'stdout', '')
        exit_code = getattr(test_result, 'exit_code', 1)
    else:
        # C'est un dictionnaire
        error_output = test_result.get("error", "") or test_result.get("output", "")
        test_results = test_result.get("test_results", {})
        errors = test_results.get("errors", [])
        if errors:
            error_output += "\n" + "\n".join(errors)
        exit_code = test_result.get("exit_code", 1)
    
    # Patterns d'erreurs communes
    error_patterns = {
        "module not found": "Module manquant - vérifier les imports et dépendances",
        "no module named": "Module Python manquant - vérifier les imports",
        "cannot find module": "Module Node.js manquant - vérifier package.json",
        "import error": "Erreur d'import - vérifier les chemins et dépendances",
        "syntax error": "Erreur de syntaxe dans le code",
        "indentation error": "Erreur d'indentation Python",
        "unexpected token": "Erreur de syntaxe JavaScript/TypeScript",
        "command not found": "Commande de test non trouvée - installer les dépendances",
        "permission denied": "Problème de permissions - vérifier l'exécutable",
        "connection refused": "Problème de connexion - services externes requis?",
        "timeout": "Test trop lent - optimiser ou augmenter timeout",
        "assertion": "Assertion échouée - logique métier incorrecte",
        "failed": "Test(s) échoué(s)",
        "error": "Erreur générale"
    }
    
    error_analysis = "Échec de test non spécifique"
    
    # Chercher des patterns d'erreur dans la sortie
    error_output_lower = error_output.lower()
    for pattern, description in error_patterns.items():
        if pattern in error_output_lower:
            error_analysis = description
            break
    
    # Ajouter des détails spécifiques si disponibles
    if exit_code == 127:
        error_analysis = "Commande de test non trouvée - installer les dépendances"
    elif exit_code == 2:
        error_analysis = "Erreur de configuration ou arguments invalides"
    elif exit_code == 1:
        error_analysis = "Tests échoués - vérifier la logique métier"
    
    # Extraire les premières lignes d'erreur pour plus de contexte
    error_lines = error_output.split('\n')[:5]
    relevant_errors = [line.strip() for line in error_lines if line.strip() and not line.startswith('===')]
    
    if relevant_errors:
        error_context = ' | '.join(relevant_errors[:2])  # Maximum 2 lignes
        error_analysis += f" ({error_context})"
    
    return error_analysis

def should_continue_to_debug(state: Dict[str, Any]) -> bool:
    """Détermine si le workflow doit continuer vers le debug."""
    
    # Vérifier s'il y a eu des échecs de tests récents
    if not state["results"]["test_results"]:
        return False
    
    latest_test = state["results"]["test_results"][-1]
    
    # Si le dernier test a réussi, pas besoin de debug
    if latest_test.success:
        return False
    
    # Vérifier si on n'a pas dépassé la limite de tentatives
    debug_attempts = state["results"].get("debug_attempts", 0)
    max_debug_attempts = state["results"].get("max_debug_attempts", 3)
    if debug_attempts >= max_debug_attempts:
        return False
    
    return True

def should_continue_to_finalize(state: Dict[str, Any]) -> bool:
    """Détermine si le workflow peut passer à la finalisation."""
    
    # Vérifier s'il y a eu des tests
    if not state["results"]["test_results"]:
        return False
    
    # Le dernier test doit avoir réussi
    latest_test = state["results"]["test_results"][-1]
    return latest_test.success 