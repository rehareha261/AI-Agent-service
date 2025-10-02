"""Workflow principal utilisant LangGraph pour l'agent de développement."""

import asyncio
import tempfile
import os
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional, AsyncIterator

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from models.state import GraphState
from models.schemas import TaskRequest, WorkflowStatus
from utils.logger import get_logger

# Import des nœuds
from nodes.prepare_node import prepare_environment
from nodes.analyze_node import analyze_requirements  
from nodes.implement_node import implement_task
from nodes.test_node import run_tests
from nodes.debug_node import debug_code
from nodes.openai_debug_node import openai_debug_after_human_request  # ✅ IMPORT CORRECT
from nodes.qa_node import quality_assurance_automation
from nodes.finalize_node import finalize_pr
from nodes.monday_validation_node import monday_human_validation
from nodes.merge_node import merge_after_validation
from nodes.update_node import update_monday

# Imports des services et configurations
from services.database_persistence_service import db_persistence
from config.workflow_limits import WorkflowLimits
from utils.langsmith_tracing import workflow_tracer
from config.langsmith_config import langsmith_config

logger = get_logger(__name__)

# Constantes du workflow
MAX_WORKFLOW_NODES = 11  # Nombre de nœuds business réels dans le workflow
TOTAL_GRAPH_NODES = 11   # ✅ CORRECTION: Le nombre total = MAX_WORKFLOW_NODES (LangGraph ajoute __start__ et __end__ automatiquement)
MAX_DEBUG_ATTEMPTS = 2   # ✅ CORRECTION: Réduire à 2 tentatives pour éviter les boucles infinies

# ✅ NOUVEAU: Configuration des timeouts et retry
WORKFLOW_TIMEOUT_SECONDS = WorkflowLimits.WORKFLOW_TIMEOUT  # Utiliser la configuration
NODE_TIMEOUT_SECONDS = 600      # 10 minutes maximum par nœud
MAX_NODE_RETRIES = 2            # Maximum 2 essais par nœud

def create_workflow_graph() -> StateGraph:
    """
    Crée et configure le graphe de workflow LangGraph pour RabbitMQ avec validation humaine.

    Le graphe suit ce flux optimisé conforme à la conception :
    START → prepare → analyze → implement → test → [debug ↔ test] → qa → finalize → human_validation → merge → update → END

    Returns:
        StateGraph configuré et prêt à être compilé
    """

    # Créer le graphe avec GraphState
    workflow = StateGraph(GraphState)

    # Ajouter tous les nœuds dans l'ordre de la conception
    workflow.add_node("prepare_environment", prepare_environment)
    workflow.add_node("analyze_requirements", analyze_requirements)
    workflow.add_node("implement_task", implement_task)
    workflow.add_node("run_tests", run_tests)
    workflow.add_node("debug_code", debug_code)
    workflow.add_node("quality_assurance_automation", quality_assurance_automation)
    workflow.add_node("finalize_pr", finalize_pr)
    workflow.add_node("monday_validation", monday_human_validation)
    workflow.add_node("openai_debug", openai_debug_after_human_request)
    workflow.add_node("merge_after_validation", merge_after_validation)
    workflow.add_node("update_monday", update_monday)

    # Définir le point d'entrée
    workflow.set_entry_point("prepare_environment")

    # Connexions principales du workflow selon la conception
    workflow.add_edge("prepare_environment", "analyze_requirements")
    workflow.add_edge("analyze_requirements", "implement_task")
    workflow.add_edge("implement_task", "run_tests")

    # Logique conditionnelle pour les tests
    workflow.add_conditional_edges(
        "run_tests",
        _should_debug,
        {
            "debug": "debug_code",      # Tests échoués → debug
            "continue": "quality_assurance_automation",  # Tests réussis → QA
            "end": END                  # Erreur critique → fin
        }
    )

    # Boucle de debug
    workflow.add_edge("debug_code", "run_tests")

    # Finalisation après QA avec validation Monday.com
    workflow.add_edge("quality_assurance_automation", "finalize_pr")
    workflow.add_edge("finalize_pr", "monday_validation")

    # Après validation Monday.com, décider du chemin
    workflow.add_conditional_edges(
        "monday_validation",
        _should_merge_or_debug_after_monday_validation,
        {
            "merge": "merge_after_validation",    # Humain a dit "oui" → merge
            "debug": "openai_debug",              # Humain a dit "non" → debug OpenAI
            "update_only": "update_monday",       # Timeout/erreur → update seulement
            "end": END                            # Erreur critique → fin
        }
    )

    # ✅ CORRECTION: Logique conditionnelle après debug OpenAI au lieu de retour automatique aux tests
    workflow.add_conditional_edges(
        "openai_debug",
        _should_continue_after_openai_debug,
        {
            "retest": "run_tests",           # Retry les tests après corrections
            "update_only": "update_monday",  # Limite atteinte → update seulement
            "end": END                       # Erreur critique → fin
        }
    )

    # Finalisation
    workflow.add_edge("merge_after_validation", "update_monday")
    workflow.add_edge("update_monday", END)

    logger.info("✅ Graphe de workflow créé et configuré pour RabbitMQ avec nouveaux nœuds")
    return workflow

def _should_merge_or_debug_after_monday_validation(state: GraphState) -> str:
    """
    Détermine le chemin après validation Monday.com.

    LOGIQUE AMÉLIORÉE:
    - "oui" + pas de problèmes → merge
    - "oui" + problèmes détectés → debug automatique (ignore la réponse humaine)
    - "non/debug" → debug OpenAI
    - timeout/erreur → update seulement

    Args:
        state: État actuel du workflow

    Returns:
        "merge" si approuvé ET aucun problème, "debug" si problèmes détectés ou debug demandé, "update_only" si erreur/timeout
    """
    # Protection: s'assurer que results existe
    results = state.get("results", {})
    if not isinstance(results, dict):
        logger.warning("⚠️ Results n'est pas un dictionnaire dans _should_merge_or_debug_after_monday_validation")
        return "update_only"

    # ✅ CORRECTION CRITIQUE: Vérifier les erreurs fatales EN PREMIER
    current_status = results.get("current_status", "")
    if current_status == "failed_validation":
        logger.error("❌ Erreur de validation critique détectée - arrêt du workflow")
        return "end"
    
    # Vérifier si le finalize_pr a échoué de manière critique
    finalize_errors = results.get("error_logs", [])
    critical_finalize_errors = [
        "URL du repository non définie",
        "Branche Git non définie", 
        "Répertoire de travail non défini",
        "Working directory non défini"
    ]
    
    for error_log in finalize_errors:
        if any(critical_error in error_log for critical_error in critical_finalize_errors):
            logger.error(f"❌ Erreur critique de finalisation détectée: {error_log}")
            logger.error("❌ Impossible de continuer le workflow - données manquantes")
            return "end"
    
    # Vérifier si GitHub push a échoué de manière critique
    if results.get("skip_github", False):
        logger.warning("⚠️ GitHub push ignoré - transition vers update Monday seulement")
        return "update_only"

    # ✅ AMÉLIORATION: Vérification et correction de cohérence d'état
    human_decision = results.get("human_decision", "error")
    should_merge = results.get("should_merge", False)
    validation_status = results.get("human_validation_status")
    error = results.get("error")

    # Détection et correction d'incohérences
    if human_decision == "approve" and not should_merge:
        logger.warning("⚠️ Incohérence détectée: approve sans should_merge - correction automatique")
        results["should_merge"] = True
        should_merge = True
    elif human_decision == "debug" and should_merge:
        logger.warning("⚠️ Incohérence détectée: debug avec should_merge=True - correction automatique")
        results["should_merge"] = False
        should_merge = False
    elif validation_status == "approve" and human_decision != "approve":
        logger.warning("⚠️ Incohérence détectée: validation_status/human_decision mismatch - correction automatique")
        results["human_decision"] = "approve"
        results["should_merge"] = True
        human_decision = "approve"
        should_merge = True
    elif validation_status == "rejected" and human_decision not in ["debug", "error", "timeout"]:
        logger.warning("⚠️ Incohérence détectée: validation rejected mais human_decision invalide - correction automatique")
        results["human_decision"] = "debug"
        results["should_merge"] = False
        human_decision = "debug"
        should_merge = False

    # Erreur critique ou timeout
    if error and "timeout" in error.lower():
        logger.warning("⚠️ Timeout validation Monday.com - update seulement")
        return "update_only"

    if human_decision == "error":
        logger.warning("⚠️ Erreur validation Monday.com - update seulement")
        return "update_only"
    
    # ✅ NOUVEAU: Gérer la validation automatique
    if human_decision == "timeout":
        logger.warning("⚠️ Timeout validation Monday.com - update seulement")
        return "update_only"
    
    # ✅ NOUVEAU: Gérer l'approbation automatique  
    if human_decision == "approve_auto":
        logger.info("✅ Validation automatique approuvée - traiter comme approve")
        human_decision = "approve"
        should_merge = True
        results["should_merge"] = True

    # ✅ NOUVELLE LOGIQUE: Vérification automatique des problèmes même si l'humain dit "oui"
    def _has_unresolved_issues(results: dict) -> tuple[bool, list[str]]:
        """Vérifie s'il y a encore des problèmes non résolus dans le workflow."""
        issues = []

        # 1. Vérifier les résultats de tests
        test_results = results.get("test_results", {})
        if isinstance(test_results, dict):
            test_success = test_results.get("success", False)
            if not test_success:
                issues.append("tests échoués")
                failed_tests = test_results.get("failed_tests", [])
                if failed_tests:
                    issues.append(f"{len(failed_tests)} test(s) en échec")

        # 2. Vérifier les erreurs de build/linting
        error_logs = results.get("error_logs", [])
        if error_logs:
            issues.append(f"{len(error_logs)} erreur(s) détectée(s)")

        # 3. Vérifier les erreurs d'implémentation
        implementation_errors = results.get("implementation_errors", [])
        if implementation_errors:
            issues.append(f"{len(implementation_errors)} erreur(s) d'implémentation")

        # 4. Vérifier si la PR a été créée
        pr_url = results.get("pr_url")
        if not pr_url:
            issues.append("pull request non créée")

        # 5. Vérifier les scores de qualité
        qa_results = results.get("qa_results", {})
        if isinstance(qa_results, dict):
            overall_score = qa_results.get("overall_score", 0)
            if overall_score < 70:  # Score minimal requis
                issues.append(f"score qualité trop bas ({overall_score}/100)")

        return len(issues) > 0, issues

    # Décision humaine de debug explicite
    if human_decision == "debug":
        logger.info("🔧 Humain demande debug via Monday.com - lancer OpenAI debug")
        return "debug"

    # Décision humaine d'approuver - mais vérifier les problèmes
    if human_decision == "approve" and should_merge:
        # ✅ NOUVELLE LOGIQUE: Vérification automatique seulement si l'humain n'a pas été explicite
        has_issues, issue_list = _has_unresolved_issues(results)

        if has_issues:
            # ✅ CORRECTION: Respecter la décision humaine explicite mais avertir
            logger.warning("⚠️ Humain a dit 'oui' mais problèmes détectés - RESPECT DE LA DÉCISION HUMAINE")
            logger.warning(f"   Problèmes détectés: {', '.join(issue_list)}")
            logger.warning("   L'humain assume la responsabilité du merge malgré les problèmes")
            
            # Ajouter un avertissement dans l'état mais continuer le merge
            if "ai_messages" not in results:
                results["ai_messages"] = []
            results["ai_messages"].append(f"⚠️ Merge approuvé malgré: {', '.join(issue_list)}")
            results["human_override"] = True
            results["override_issues"] = issue_list
            
            return "merge"  # ✅ CORRECTION: Respecter la décision humaine
        else:
            logger.info("✅ Humain a dit 'oui' et aucun problème détecté - MERGE")
            return "merge"

    # Timeout ou autre
    if human_decision == "timeout":
        logger.info("⏰ Timeout validation Monday.com - update seulement")
        return "update_only"

    # Par défaut, update seulement
    logger.info(f"🤷 Décision inconnue ({human_decision}) - update seulement")
    return "update_only"

def _should_merge_after_validation(state: GraphState) -> str:
    """
    Détermine si le workflow doit procéder au merge après validation humaine.

    Args:
        state: État actuel du workflow

    Returns:
        "merge" si approuvé, "skip_merge" si rejeté, "end" si erreur critique
    """
    # Protection: s'assurer que results existe
    results = state.get("results", {})
    if not isinstance(results, dict):
        logger.warning("⚠️ Results n'est pas un dictionnaire dans _should_merge_after_validation")
        return "end"

    # Vérifier si on a une réponse de validation
    should_merge = results.get("should_merge", False)
    validation_status = results.get("human_validation_status")
    error = results.get("error")

    # Erreur critique
    if error and "timeout" in error.lower():
        logger.warning("⚠️ Timeout validation humaine - arrêt du workflow")
        return "end"

    # Validation approuvée
    if should_merge and validation_status == "approve":
        logger.info("✅ Validation approuvée - procéder au merge")
        return "merge"

    # Validation rejetée ou expirée
    logger.info(f"⏭️ Validation non approuvée ({validation_status}) - passer au update Monday")
    return "skip_merge"

def _should_debug(state: GraphState) -> str:
    """
    Détermine si le workflow doit passer en mode debug.

    Args:
        state: État actuel du workflow

    Returns:
        "debug" si debug nécessaire, "continue" si on peut passer à QA, "end" si erreur critique
    """
    # Importer les limites configurées
    from config.workflow_limits import WorkflowLimits

    # Protection: s'assurer que results existe
    results = state.get("results", {})
    if not isinstance(results, dict):
        logger.warning("⚠️ Results n'est pas un dictionnaire dans _should_debug")
        return "end"

    # Vérifier si on a des résultats de tests
    if not results or "test_results" not in results:
        logger.warning("⚠️ Aucun résultat de test trouvé - Structure de données incorrecte")
        results["current_status"] = "error_no_test_structure"
        results["error"] = "Structure de données de test manquante"
        results["should_continue"] = False
        return "end"  # ARRÊT PROPRE car problème structurel

    test_results_list = results["test_results"]

    # Si aucun test n'a été exécuté (liste vide)
    if not test_results_list:
        logger.info("📝 Aucun test exécuté - Continuation vers assurance qualité")
        results["no_tests_found"] = True
        results["test_status"] = "no_tests"
        if "ai_messages" not in results:
            results["ai_messages"] = []
        results["ai_messages"].append("📝 Aucun test exécuté - Passage direct à l'assurance qualité")
        return "continue"  # ✅ Continuer vers QA au lieu d'arrêter

    # ✅ CORRECTION CRITIQUE: Prendre SEULEMENT le dernier résultat de test
    # Éviter l'accumulation des échecs des cycles précédents
    if isinstance(test_results_list, list):
        latest_test_result = test_results_list[-1]  # Seulement le plus récent
    else:
        latest_test_result = test_results_list  # Au cas où ce serait un seul résultat

    logger.info(f"🔍 Analyse du dernier résultat de test: {type(latest_test_result)}")

    # Analyser le DERNIER résultat de test uniquement
    tests_passed = False
    failed_count = 0
    total_tests = 0

    if isinstance(latest_test_result, dict):
        # Format : {"success": bool, "total_tests": int, "failed_tests": [...], ...}
        tests_passed = latest_test_result.get("success", False)
        total_tests = latest_test_result.get("total_tests", 0)
        failed_count = latest_test_result.get("failed_tests", 0)

        # Détecter le flag spécial "no_tests_found"
        if latest_test_result.get("no_tests_found", False):
            logger.info("📝 Flag 'no_tests_found' détecté - Continuation vers assurance qualité")
            results["no_tests_found"] = True
            results["test_status"] = "no_tests"
            if "ai_messages" not in results:
                results["ai_messages"] = []
            results["ai_messages"].append("📝 Aucun test trouvé - Passage direct à l'assurance qualité")
            return "continue"  # ✅ Continuer vers QA au lieu d'arrêter

        # Si c'est un nombre, c'est le nombre d'échecs
        if isinstance(failed_count, int):
            pass  # failed_count est déjà un int
        elif isinstance(failed_count, list):
            failed_count = len(failed_count)
        else:
            failed_count = 0

    elif hasattr(latest_test_result, 'success'):
        # C'est un objet TestResult
        tests_passed = latest_test_result.success
        total_tests = getattr(latest_test_result, 'total_tests', 1)
        failed_count = getattr(latest_test_result, 'failed_tests', 0) if not tests_passed else 0
    else:
        # Format booléen simple
        tests_passed = bool(latest_test_result)
        total_tests = 1
        failed_count = 0 if tests_passed else 1

    # CAS SPÉCIAL : Si total_tests = 0, continuer vers QA avec un flag spécial
    if total_tests == 0:
        logger.info("📝 Aucun test trouvé (0/0) - Continuation vers assurance qualité")
        results["no_tests_found"] = True
        results["test_status"] = "no_tests"
        if "ai_messages" not in results:
            results["ai_messages"] = []
        results["ai_messages"].append("📝 Aucun test trouvé - Passage direct à l'assurance qualité")
        return "continue"  # ✅ Continuer vers QA au lieu d'arrêter

    # SYSTÈME DE COMPTAGE ROBUSTE DES TENTATIVES DE DEBUG
    # Initialiser le compteur s'il n'existe pas
    if "debug_attempts" not in results:
        results["debug_attempts"] = 0

    debug_attempts = results["debug_attempts"]
    MAX_DEBUG_ATTEMPTS = WorkflowLimits.MAX_DEBUG_ATTEMPTS

    logger.info(f"🔧 Debug attempts: {debug_attempts}/{MAX_DEBUG_ATTEMPTS}, Tests: {total_tests} total, {failed_count} échecs (dernier résultat uniquement)")

    # LOGIQUE DE DÉCISION SIMPLIFIÉE ET ROBUSTE
    if tests_passed:
        logger.info("✅ Tests réussis - passage à l'assurance qualité")
        return "continue"

    if debug_attempts >= MAX_DEBUG_ATTEMPTS:
        logger.warning(f"⚠️ Limite de debug atteinte ({debug_attempts}/{MAX_DEBUG_ATTEMPTS}) - passage forcé à QA")
        results["error"] = f"Tests échoués après {debug_attempts} tentatives de debug"
        return "continue"  # FORCÉ vers QA au lieu de boucler

    # Incrémenter le compteur AVANT de retourner "debug"
    results["debug_attempts"] += 1
    logger.info(f"🔧 Tests échoués ({failed_count} échecs) - lancement debug {results['debug_attempts']}/{MAX_DEBUG_ATTEMPTS}")
    return "debug"

def _should_continue_after_openai_debug(state: GraphState) -> str:
    """
    Détermine le chemin après debug OpenAI suite à validation humaine.
    
    LOGIQUE:
    - Si limite de debug atteinte → update_only
    - Si debug réussi → retest 
    - Si erreur critique → end
    
    Args:
        state: État actuel du workflow
        
    Returns:
        "retest" pour retester, "update_only" si limite atteinte, "end" si erreur critique
    """
    results = state.get("results", {})
    if not isinstance(results, dict):
        logger.warning("⚠️ Results n'est pas un dictionnaire dans _should_continue_after_openai_debug")
        return "end"
    
    # Vérifier si la limite de debug après validation humaine est atteinte
    if results.get("debug_limit_reached", False):
        logger.warning("⚠️ Limite de debug après validation humaine atteinte - update Monday seulement")
        return "update_only"
    
    # Vérifier si le debug a échoué
    if results.get("openai_debug_failed", False):
        logger.error("❌ Debug OpenAI a échoué - update Monday seulement")
        return "update_only"
    
    # Vérifier si on doit continuer le workflow
    if not results.get("should_continue", True):
        logger.warning("⚠️ Workflow marqué pour arrêt - update Monday seulement")
        return "update_only"
    
    # Si debug réussi, retester
    if results.get("openai_debug_completed", False):
        logger.info("✅ Debug OpenAI terminé avec succès - relance des tests")
        return "retest"
    
    # Par défaut, retester
    logger.info("🔄 Debug OpenAI terminé - relance des tests")
    return "retest"

async def run_workflow(task_request: TaskRequest) -> Dict[str, Any]:
    """
    Execute un workflow complet pour une tâche donnée avec RabbitMQ.

    Args:
        task_request: Requête de tâche à traiter

    Returns:
        Résultat du workflow avec métriques
    """
    workflow_id = f"workflow_{task_request.task_id}_{int(datetime.now().timestamp())}"

    logger.info(f"🚀 Démarrage workflow {workflow_id} pour: {task_request.title}")

    # ✅ NOUVEAU: Protéger le workflow entier avec un timeout global
    try:
        return await asyncio.wait_for(
            _run_workflow_with_recovery(workflow_id, task_request),
            timeout=WORKFLOW_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        logger.error(f"❌ Timeout global du workflow {workflow_id} après {WORKFLOW_TIMEOUT_SECONDS}s")
        return _create_timeout_result(task_request, workflow_id, "global_timeout")
    except Exception as e:
        logger.error(f"❌ Erreur critique dans le workflow {workflow_id}: {e}", exc_info=True)
        return _create_error_result(task_request, str(e))

async def _run_workflow_with_recovery(workflow_id: str, task_request: TaskRequest) -> Dict[str, Any]:
    """Execute le workflow avec gestion de récupération d'état."""

    # Initialiser la persistence si nécessaire
    if not db_persistence.pool:
        await db_persistence.initialize()

    # ✅ CORRECTION: Déclarer toutes les variables au début du scope
    task_db_id = None
    actual_task_run_id = None  # ID entier de la base
    uuid_task_run_id = None    # UUID pour LangSmith
    # Générer task_run_id unique immédiatement
    task_run_id = f"run_{uuid.uuid4().hex[:12]}_{int(time.time())}"

    try:
        # Si task_request contient un monday_item_id, créer la tâche
        if hasattr(task_request, 'monday_item_id'):
            monday_payload = {
                "pulseId": task_request.monday_item_id,
                "pulseName": task_request.title,
                "boardId": getattr(task_request, 'board_id', None),
                "columnValues": {}
            }
            task_db_id = await db_persistence.create_task_from_monday(monday_payload)
            logger.info(f"✅ Tâche créée en base: task_db_id={task_db_id}")

        # ✅ TOUJOURS créer un task_run en base, même si task_db_id=None
        logger.info(f"🔄 Tentative création task_run avec task_db_id={task_db_id}, task_run_id={task_run_id}")
        actual_task_run_id = await db_persistence.start_task_run(
            task_db_id,  # peut être None si pas de Monday
            workflow_id,
            task_run_id
        )

        if actual_task_run_id:
            uuid_task_run_id = task_run_id
            logger.info(f"✅ Task run créé: actual_id={actual_task_run_id}, uuid={uuid_task_run_id}")
        else:
            logger.warning("⚠️ Aucun task_run_id généré - workflow sans persistence")

        # ✅ NOUVEAU: Créer un état initial enrichi avec recovery
        initial_state = _create_initial_state_with_recovery(task_request, workflow_id, actual_task_run_id, uuid_task_run_id)

                # Créer et compiler le graphe
        workflow_graph = create_workflow_graph()
        
        # Compiler avec un checkpointer pour gérer l'état
        checkpointer = MemorySaver()
        compiled_graph = workflow_graph.compile(checkpointer=checkpointer)
        
        # Exécuter le workflow avec monitoring
        workflow_start_time = time.time()
        final_state = None
        status = "unknown"
        success = False
        workflow_error = None

        # ✅ NOUVEAU: Exécuter avec gestion de récupération
        async for event in _execute_workflow_with_recovery(compiled_graph, initial_state, workflow_id):
            event_type = event.get("type")

            if event_type == "step":
                node_name = event.get("node")
                node_output = event.get("output")
                logger.info(f"🔄 Exécution du nœud: {node_name}")

                # ✅ NOUVEAU: Sauvegarder l'état après chaque nœud
                await _save_node_checkpoint(actual_task_run_id, node_name, node_output)
                
                # ✅ CORRECTION: Mettre à jour final_state à chaque étape
                final_state = node_output
                
                # ✅ VÉRIFICATION: Si c'est le dernier nœud (update_monday), marquer comme terminé
                if node_name == "update_monday":
                    status = final_state.get("results", {}).get("current_status", "completed")
                    success = final_state.get("results", {}).get("success", True)
                    workflow_error = final_state.get("results", {}).get("error", None)
                    logger.info(f"🏁 Dernier nœud exécuté (update_monday). Statut: {status}, Succès: {success}")
                    # Ne pas break ici, laisser le workflow se terminer naturellement

            elif event_type == "error":
                logger.error(f"❌ Erreur dans le workflow: {event.get('error')}")
                workflow_error = event.get('error')
                final_state = event.get("state", initial_state)
                status = "failed"
                success = False
                break

            elif event_type == "end":
                final_state = event["output"]
                status = final_state.get("results", {}).get("current_status", "completed")
                success = final_state.get("results", {}).get("success", True)
                workflow_error = final_state.get("results", {}).get("error", None)
                if workflow_error:
                    success = False # Si une erreur est présente, ce n'est pas un succès
                logger.info(f"🏁 Workflow terminé via END. Statut: {status}, Succès: {success}")
                break

        # ✅ AMÉLIORATION: Meilleure gestion de l'état final
        if final_state is None:
            final_state = initial_state # Utiliser l'état initial comme fallback
            workflow_error = "Workflow terminé sans état final clair"
            success = False
            status = "failed"
            logger.error(f"❌ {workflow_error}")
        else:
            # ✅ NOUVEAU: Vérification finale de l'état
            if not isinstance(final_state, dict):
                logger.warning(f"⚠️ État final inattendu (type: {type(final_state)}), conversion en dict")
                final_state = {"results": {}, "error": "État final invalide"}
                success = False
                status = "failed"
            
            # Si pas encore déterminé, extraire du final_state
            if 'success' not in locals() or success is None:
                success = final_state.get("results", {}).get("success", True)
            if 'status' not in locals() or status == "unknown":
                status = final_state.get("results", {}).get("current_status", "completed")
            if 'workflow_error' not in locals():
                workflow_error = final_state.get("results", {}).get("error", None)
            
            logger.info(f"✅ État final traité: status={status}, success={success}, error={workflow_error}")

        duration = time.time() - workflow_start_time

        # ✅ NOUVEAU: Finaliser la persistence avec état de récupération
        await _finalize_workflow_run(actual_task_run_id, success, workflow_error, final_state)

        # Retourner le résultat final du workflow
        return _create_workflow_result(task_request, final_state, duration, success, workflow_error)

    except Exception as e:
        logger.error(f"❌ Erreur critique workflow {workflow_id}: {e}", exc_info=True)
        return _create_error_result(task_request, str(e))

async def _execute_workflow_with_recovery(compiled_graph, initial_state: Dict[str, Any], workflow_id: str) -> AsyncIterator[Dict[str, Any]]:
    """Execute le workflow nœud par nœud avec récupération d'erreur."""

    node_count = 0
    max_nodes = WorkflowLimits.MAX_NODES_SAFETY_LIMIT

    try:
        async for event in compiled_graph.astream(initial_state, config={"configurable": {"thread_id": workflow_id}}):
            node_count += 1

            # Vérifier la limite de nœuds
            if node_count > max_nodes:
                logger.error(f"⚠️ Limite de nœuds atteinte ({node_count}/{max_nodes}) - arrêt du workflow")
                yield {
                    "type": "error",
                    "error": f"Arrêt forcé - limite de {max_nodes} nœuds atteinte",
                    "state": initial_state
                }
                return

            # ✅ NOUVEAU: Timeout par nœud avec retry
            try:
                yield await asyncio.wait_for(_process_node_event(event), timeout=NODE_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ Timeout du nœud après {NODE_TIMEOUT_SECONDS}s - tentative de récupération")

                # Tenter de récupérer avec l'état actuel
                yield {
                    "type": "error",
                    "error": f"Timeout du nœud après {NODE_TIMEOUT_SECONDS}s",
                    "state": event.get("output", initial_state)
                }
                return

    except Exception as e:
        logger.error(f"❌ Erreur lors de l'exécution du workflow: {e}", exc_info=True)
        yield {
            "type": "error",
            "error": str(e),
            "state": initial_state
        }

async def _process_node_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Traite un événement de nœud avec logging."""
    # Vérifier d'abord si c'est un événement de fin
    if "__end__" in event:
        return {
            "type": "end",
            "output": event.get("__end__", event)
        }
    
    # Sinon, traiter les nœuds normaux
    for node_name, node_output in event.items():
        if node_name != "__end__":
            return {
                "type": "step",
                "node": node_name,
                "output": node_output
            }

    # Si aucun nœud trouvé, considérer comme fin
    return {
        "type": "end",
        "output": event
    }

def _create_initial_state_with_recovery(task_request: TaskRequest, workflow_id: str, actual_task_run_id: Optional[int], uuid_task_run_id: Optional[str]) -> Dict[str, Any]:
    """Crée l'état initial avec support de récupération."""

    initial_state = {
        "task": task_request,
        "workflow_id": workflow_id,
        "run_id": actual_task_run_id,
        "uuid_run_id": uuid_task_run_id,
        "results": {},
        "error": None,
        "current_node": None,
        "completed_nodes": [],
        "node_retry_count": {},  # ✅ NOUVEAU: Compteur de retry par nœud
        "recovery_mode": False,  # ✅ NOUVEAU: Mode récupération
        "checkpoint_data": {}    # ✅ NOUVEAU: Données de checkpoint
    }

    return initial_state

async def _save_node_checkpoint(task_run_id: Optional[int], node_name: str, node_output: Dict[str, Any]):
    """Sauvegarde un checkpoint après chaque nœud."""
    if not task_run_id:
        return

    try:
        checkpoint_data = {
            "node_name": node_name,
            "completed_at": datetime.now().isoformat(),
            "output_summary": {
                "has_results": bool(node_output.get("results")),
                "has_error": bool(node_output.get("error")),
                "current_status": node_output.get("results", {}).get("current_status", "unknown")
            }
        }

        await db_persistence.save_node_checkpoint(task_run_id, node_name, checkpoint_data)
        logger.debug(f"💾 Checkpoint sauvé pour {node_name}")

    except Exception as e:
        logger.warning(f"⚠️ Erreur sauvegarde checkpoint {node_name}: {e}")

async def _finalize_workflow_run(task_run_id: Optional[int], success: bool, error: Optional[str], final_state: Dict[str, Any]):
    """Finalise le workflow run avec l'état final."""
    if not task_run_id:
        return

    try:
        # Calculer les métriques finales
        metrics = {
            "success": success,
            "error": error,
            "completed_nodes": final_state.get("completed_nodes", []),
            "final_status": final_state.get("results", {}).get("current_status", "unknown")
        }

        status = "completed" if success else "failed"
        await db_persistence.complete_task_run(task_run_id, status, metrics, error)
        logger.info(f"✅ Workflow run {task_run_id} finalisé")

    except Exception as e:
        logger.error(f"❌ Erreur finalisation workflow run {task_run_id}: {e}")

def _create_timeout_result(task_request: TaskRequest, workflow_id: str, timeout_type: str) -> Dict[str, Any]:
    """Crée un résultat pour un timeout de workflow."""
    return {
        "success": False,
        "status": "timeout",
        "error": f"Timeout {timeout_type} du workflow",
        "workflow_id": workflow_id,
        "task_id": task_request.task_id,
        "task_title": task_request.title,
        "duration": WORKFLOW_TIMEOUT_SECONDS if timeout_type == "global_timeout" else NODE_TIMEOUT_SECONDS,
        "results": {
            "current_status": "timeout",
            "error": f"Workflow interrompu par timeout {timeout_type}",
            "success": False
        }
    }

def _create_initial_state(task_request: TaskRequest, workflow_id: str, task_db_id: Optional[int] = None, actual_task_run_id: Optional[int] = None) -> GraphState:
    """Crée l'état initial du workflow sous forme de TypedDict."""
    return {
        "workflow_id": workflow_id,
        "status": WorkflowStatus.PENDING,
        "current_node": None,
        "completed_nodes": [],
        "task": task_request,
        "db_task_id": task_db_id,  # Ajout direct
        "db_run_id": actual_task_run_id, # Ajout direct
        "results": {
            "ai_messages": [],
            "error_logs": [],
            "modified_files": [],
            "test_results": [],
            "debug_attempts": 0
        },
        "error": None,
        "started_at": datetime.now(),
        "completed_at": None
    }

def _process_final_result(final_state: GraphState, task_request: TaskRequest) -> Dict[str, Any]:
    """
    Traite l'état final du workflow et génère le résultat.

    Args:
        final_state: État final du workflow
        task_request: Requête de tâche originale

    Returns:
        Dictionnaire avec le résultat du workflow
    """

    # ✅ CORRECTION: Logique de succès plus nuancée et tolérante
    current_status = final_state.get('status', WorkflowStatus.PENDING)
    results = final_state.get("results") or {}
    completed_nodes = final_state.get("completed_nodes") or []
    error_message = final_state.get("error")

    # Critères de succès améliorés (plus tolerants)
    success = False

    if current_status == WorkflowStatus.COMPLETED:
        success = True
    elif len(completed_nodes) >= 3:  # Au moins 3 nœuds complétés = succès partiel
        # Vérifier si des étapes importantes sont terminées
        important_nodes = ["requirements_analysis", "code_generation", "quality_assurance"]
        completed_important = sum(1 for node in important_nodes if node in completed_nodes)

        if completed_important >= 2:  # Au moins 2 étapes importantes
            success = True
            logger.info(f"🟡 Succès partiel - {completed_important}/3 étapes importantes complétées")

    # Réévaluer le succès même en cas d'erreur si beaucoup d'étapes sont terminées
    if not success and len(completed_nodes) >= 5:
        # Si beaucoup d'étapes sont faites mais qu'il y a une erreur finale (ex: tests)
        if any(key in results for key in ["code_changes", "pr_info", "quality_assurance"]):
            success = True
            logger.info(f"🟡 Succès avec erreurs mineures - {len(completed_nodes)} nœuds complétés")

    # Calculer la durée
    duration = 0
    started_at = final_state.get("started_at")
    if started_at:
        end_time = final_state.get("completed_at") or datetime.now()
        duration = (end_time - started_at).total_seconds()

    # Les variables sont déjà définies plus haut, pas besoin de les redéfinir

    # Extraire les métriques depuis les résultats
    pr_url = None
    if "pr_info" in results:
        pr_info = results["pr_info"]
        if isinstance(pr_info, dict):
            pr_url = pr_info.get("pr_url")
        else:
            pr_url = getattr(pr_info, "pr_url", None)

    # Calculer des métriques enrichies
    files_modified = 0
    tests_executed = 0
    qa_score = 0
    analysis_score = 0

    if "code_changes" in results:
        files_modified = len(results["code_changes"]) if isinstance(results["code_changes"], dict) else 0

    if "test_results" in results:
        test_results = results["test_results"]
        if isinstance(test_results, dict):
            tests_executed = test_results.get("total_tests", 0)
        elif isinstance(test_results, list):
            tests_executed = len(test_results)
        elif hasattr(test_results, 'total_tests'):
            # C'est un objet TestResult, extraire l'attribut
            tests_executed = getattr(test_results, 'total_tests', 0)

    # Métriques QA
    if "quality_assurance" in results:
        qa_data = results["quality_assurance"]
        qa_score = qa_data.get("qa_summary", {}).get("overall_score", 0)

    # Métriques d'analyse
    if "requirements_analysis" in results:
        analysis_data = results["requirements_analysis"]
        analysis_score = analysis_data.get("complexity_score", 5)

    # Construire le résultat enrichi
    result = {
        "success": success,
        "status": current_status.value if current_status else "unknown",
        "workflow_id": final_state.get("workflow_id"),
        "task_id": task_request.task_id,
        "duration": duration,
        "completed_nodes": completed_nodes,
        "pr_url": pr_url,
        "error": error_message,
        "metrics": {
            "files_modified": files_modified,
            "tests_executed": tests_executed,
            "nodes_completed": len(completed_nodes),
            "duration_seconds": duration,
            "qa_score": qa_score,
            "analysis_complexity": analysis_score,
            "workflow_completeness": len(completed_nodes) / MAX_WORKFLOW_NODES * 100  # 11 nœuds au total
        },
        "results": results
    }

    logger.info(f"📊 Workflow terminé - Succès: {success}, Durée: {duration:.1f}s, Nœuds: {len(completed_nodes)}, QA: {qa_score}")

    return result

def _create_error_result(task_request: TaskRequest, error_msg: str) -> Dict[str, Any]:
    """Crée un résultat d'erreur standardisé."""

    return {
        "success": False,
        "status": "failed",
        "workflow_id": f"error_{task_request.task_id}",
        "task_id": task_request.task_id,
        "duration": 0,
        "completed_nodes": [],
        "pr_url": None,
        "error": error_msg,
        "metrics": {
            "files_modified": 0,
            "tests_executed": 0,
            "nodes_completed": 0,
            "duration_seconds": 0,
            "qa_score": 0,
            "analysis_complexity": 0,
            "workflow_completeness": 0
        },
        "results": {}
    }

def _ensure_final_state(state: GraphState) -> GraphState:
    """
    Garantit que l'état final est bien défini avec tous les champs requis.

    Args:
        state: État du workflow (potentiellement incomplet)

    Returns:
        État complété avec tous les champs requis pour un résultat final
    """
    if not isinstance(state, dict):
        # Créer un état minimal si state n'est pas un dict
        state = {}

    # Assurer que les champs de base existent
    if "workflow_id" not in state:
        state["workflow_id"] = f"unknown_{int(time.time())}"

    if "status" not in state:
        state["status"] = WorkflowStatus.FAILED

    if "results" not in state:
        state["results"] = {}

    # Assurer que results contient les champs requis
    results = state["results"]
    required_result_fields = [
        "ai_messages", "error_logs", "modified_files",
        "test_results", "debug_attempts", "current_status",
        "success"
    ]

    for field in required_result_fields:
        if field not in results:
            if field == "success":
                results[field] = False
            elif field == "current_status":
                results[field] = "failed"
            elif field in ["ai_messages", "error_logs", "modified_files", "test_results"]:
                results[field] = []
            elif field == "debug_attempts":
                results[field] = 0

    # Assurer un message d'erreur si absent
    if "error" not in state and not results.get("success", False):
        state["error"] = "Workflow terminé sans état final clair"
        results["error"] = state["error"]

    # Timestamps de début/fin
    if "started_at" not in state:
        state["started_at"] = datetime.now()

    if "completed_at" not in state:
        state["completed_at"] = datetime.now()

    # Liste des nœuds complétés
    if "completed_nodes" not in state:
        state["completed_nodes"] = []

    logger.info(f"✅ État final normalisé: succès={results.get('success')}, status={results.get('current_status')}")

    return state

def _create_workflow_result(task_request: TaskRequest, final_state: Dict[str, Any], duration: float, success: bool, error: Optional[str]) -> Dict[str, Any]:
    """Crée le résultat final du workflow."""

    # Extraire les informations importantes avec protection des types
    if isinstance(final_state, dict):
        final_results = final_state.get("results", {})
        completed_nodes = final_state.get("completed_nodes", [])
    else:
        # Si c'est un objet GraphState
        final_results = getattr(final_state, "results", {})
        completed_nodes = getattr(final_state, "completed_nodes", [])

    # Extraire les métriques depuis les résultats
    pr_url = None
    if "pr_info" in final_results:
        pr_info = final_results["pr_info"]
        if isinstance(pr_info, dict):
            pr_url = pr_info.get("pr_url")
        else:
            pr_url = getattr(pr_info, "pr_url", None)

    # Calculer des métriques enrichies
    files_modified = 0
    tests_executed = 0

    if "code_changes" in final_results:
        files_modified = len(final_results["code_changes"]) if isinstance(final_results["code_changes"], dict) else 0

    if "test_results" in final_results:
        test_results = final_results["test_results"]
        if isinstance(test_results, dict):
            tests_executed = test_results.get("total_tests", 0)
        elif isinstance(test_results, list):
            tests_executed = len(test_results)

    return {
        "success": success,
        "status": "completed" if success else "failed",
        "error": error,
        "workflow_id": final_state.get("workflow_id", "unknown"),
        "task_id": task_request.task_id,
        "task_title": task_request.title,
        "duration": duration,
        "completed_nodes": completed_nodes,
        "files_modified": files_modified,
        "tests_executed": tests_executed,
        "pr_url": pr_url,
        "results": final_results
    }
