"""Nœud de validation humaine via Monday.com updates."""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from models.state import GraphState
from models.schemas import HumanValidationRequest, PullRequestInfo
from services.monday_validation_service import monday_validation_service
from services.human_validation_service import validation_service as human_validation_service
from utils.logger import get_logger
from config.langsmith_config import langsmith_config
import json

logger = get_logger(__name__)


def _convert_test_results_to_dict(test_results) -> Optional[Dict[str, Any]]:
    """
    Convertit test_results en dictionnaire compatible avec HumanValidationRequest.
    
    Args:
        test_results: Peut être une liste ou un dictionnaire
        
    Returns:
        Dictionnaire structuré ou None
    """
    if not test_results:
        return None
    
    # Si déjà un dict, retourner tel quel
    if isinstance(test_results, dict):
        return test_results
    
    # Si c'est une liste, convertir en dict avec structure
    if isinstance(test_results, list):
        return {
            "tests": test_results,
            "count": len(test_results),
            "summary": f"{len(test_results)} test(s) exécuté(s)",
            "success": all(
                test.get("success", False) if isinstance(test, dict) else False 
                for test in test_results
            )
        }
    
    # Fallback: encapsuler dans un dict
    return {"raw": str(test_results), "type": str(type(test_results))}


async def monday_human_validation(state: GraphState) -> GraphState:
    """
    Nœud de validation humaine via Monday.com.
    
    Ce nœud :
    1. Poste une update dans Monday.com avec les résultats
    2. Attend une reply humaine ("oui"/"non") 
    3. Analyse la réponse avec IA intelligente
    4. Détermine la suite du workflow (merge ou debug)
    
    Args:
        state: État actuel du graphe
        
    Returns:
        État mis à jour avec la décision humaine
    """
    logger.info(f"🤝 Validation humaine Monday.com pour: {state['task'].title}")
    
    # ✅ CORRECTION CRITIQUE: Assurer l'intégrité de l'état dès le début
    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)

    # Initialiser ai_messages si nécessaire
    if "ai_messages" not in state["results"]:
        state["results"]["ai_messages"] = []
    
    state["results"]["ai_messages"].append("🤝 Posting update de validation dans Monday.com...")
    
    try:
        # ✅ CORRECTION: Vérifier la configuration Monday.com avant validation
        if not hasattr(monday_validation_service.monday_tool, 'api_token') or not monday_validation_service.monday_tool.api_token:
            logger.info("💡 Monday.com non configuré - validation humaine automatiquement approuvée")
            state["results"]["human_decision"] = "approved"
            state["results"]["human_reply"] = "Auto-approuvé (Monday.com non configuré)"
            state["results"]["validation_skipped"] = "Configuration Monday.com manquante"
            return state
        
        # 1. Préparer les résultats du workflow pour l'update
        workflow_results = _prepare_workflow_results(state)
        
        # Ajouter le validation_id aux workflow_results s'il existe déjà
        if "validation_id" in state.get("results", {}):
            workflow_results["validation_id"] = state["results"]["validation_id"]
        
        # 2. Créer la demande de validation en base de données AVANT de poster sur Monday.com
        try:
            validation_id = f"val_{state['task'].task_id}_{int(datetime.now().timestamp())}"
            
            # Préparer les informations de PR
            pr_info_obj = None
            pr_info_dict = workflow_results.get("pr_info") or state.get("results", {}).get("pr_info")
            if pr_info_dict:
                pr_info_obj = PullRequestInfo(
                    number=pr_info_dict.get("number", 0) if isinstance(pr_info_dict, dict) else getattr(pr_info_dict, "number", 0),
                    title=pr_info_dict.get("title", "") if isinstance(pr_info_dict, dict) else getattr(pr_info_dict, "title", ""),
                    url=pr_info_dict.get("url", "") if isinstance(pr_info_dict, dict) else getattr(pr_info_dict, "url", ""),
                    branch=pr_info_dict.get("branch", "") if isinstance(pr_info_dict, dict) else getattr(pr_info_dict, "branch", ""),
                    base_branch=pr_info_dict.get("base_branch", "main") if isinstance(pr_info_dict, dict) else getattr(pr_info_dict, "base_branch", "main"),
                    status=pr_info_dict.get("status", "open") if isinstance(pr_info_dict, dict) else getattr(pr_info_dict, "status", "open"),
                    created_at=datetime.now()
                )
            
            # Récupérer le code généré depuis modified_files
            modified_files_raw = workflow_results.get("modified_files", [])
            generated_code = {}
            code_changes = state.get("results", {}).get("code_changes", {})
            if code_changes:
                generated_code = code_changes
            
            # ✅ CORRECTION: S'assurer que files_modified est toujours une liste de strings
            # Si modified_files est un dict (code_changes), extraire les clés
            if isinstance(modified_files_raw, dict):
                modified_files = list(modified_files_raw.keys())
                logger.info(f"✅ Conversion dict -> list pour files_modified: {len(modified_files)} fichiers")
            elif isinstance(modified_files_raw, list):
                modified_files = modified_files_raw
            else:
                # Fallback pour types inattendus
                modified_files = []
                logger.warning(f"⚠️ Type inattendu pour modified_files: {type(modified_files_raw)}")
            
            # ✅ CORRECTION ERREUR 1: Convertir generated_code en JSON string pour la DB
            # La base de données attend un string JSON, pas un dict Python
            generated_code_dict = generated_code if generated_code else {"summary": "Code généré - voir fichiers modifiés"}
            generated_code_str = json.dumps(
                generated_code_dict,
                ensure_ascii=False,
                indent=2
            )
            logger.info(f"✅ Conversion generated_code dict -> JSON string ({len(generated_code_str)} caractères)")
            
            # ✅ CORRECTION SIMILAIRE: Convertir test_results en JSON string pour la DB
            test_results_dict = _convert_test_results_to_dict(workflow_results.get("test_results"))
            test_results_str = json.dumps(
                test_results_dict if test_results_dict else {},
                ensure_ascii=False,
                indent=2
            )
            logger.info(f"✅ Conversion test_results dict -> JSON string ({len(test_results_str)} caractères)")
            
            # ✅ CORRECTION PR_INFO: Convertir pr_info en JSON string pour la DB
            if pr_info_obj:
                # Convertir l'objet PullRequestInfo en JSON string
                pr_info_str = json.dumps(
                    pr_info_obj.model_dump() if hasattr(pr_info_obj, 'model_dump') else pr_info_obj.dict(),
                    ensure_ascii=False,
                    indent=2,
                    default=str  # Pour gérer les datetime
                )
                logger.info(f"✅ Conversion pr_info object -> JSON string ({len(pr_info_str)} caractères)")
            else:
                pr_info_str = None
            
            # Créer la demande de validation
            # ✅ COHÉRENCE: task_id dans HumanValidationRequest = Monday item ID (pour affichage UI)
            display_task_id = str(state["task"].monday_item_id) if hasattr(state["task"], 'monday_item_id') and state["task"].monday_item_id else str(state["task"].task_id)
            
            validation_request = HumanValidationRequest(
                validation_id=validation_id,
                workflow_id=state.get("workflow_id", ""),
                task_id=display_task_id,  # Monday item ID pour l'affichage UI
                task_title=state["task"].title,
                generated_code=generated_code_str,  # ✅ STRING au lieu de DICT
                code_summary=f"Implémentation de: {state['task'].title}",
                files_modified=modified_files,
                original_request=state["task"].description or state["task"].title,
                implementation_notes="\n".join(workflow_results.get("ai_messages", [])[-5:]),  # 5 derniers messages
                test_results=test_results_str,  # ✅ STRING au lieu de DICT
                pr_info=pr_info_str,  # ✅ STRING au lieu de OBJET
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=10),  # Expire dans 10 minutes
                requested_by="ai_agent"
            )
            
            # Initialiser le service si nécessaire
            if not human_validation_service.db_pool:
                await human_validation_service.init_db_pool()
            
            # ✅ NOMENCLATURE CLARIFIÉE:
            # - display_task_id (ci-dessus) = Monday item ID (5028673529) pour affichage UI
            # - task_id_int (ci-dessous) = tasks_id de la DB (36) pour foreign key
            # La table human_validations.task_id référence tasks.tasks_id, PAS tasks.monday_item_id
            task_id_int = state.get("db_task_id")
            
            # ✅ NOUVEAU: Fallback pour récupérer task_id depuis la DB si manquant dans state
            if not task_id_int:
                logger.warning(f"⚠️ db_task_id manquant dans state - tentative récupération depuis DB")
                
                # Essayer de récupérer depuis monday_item_id
                monday_item_id = state["task"].monday_item_id if hasattr(state["task"], 'monday_item_id') else state["task"].task_id
                
                if human_validation_service.db_pool:
                    try:
                        async with human_validation_service.db_pool.acquire() as conn:
                            task_id_int = await conn.fetchval("""
                                SELECT tasks_id FROM tasks WHERE monday_item_id = $1
                            """, int(monday_item_id))
                            
                            if task_id_int:
                                logger.info(f"✅ task_id récupéré depuis DB: {task_id_int} (monday_item_id={monday_item_id})")
                                # Mettre à jour state pour les prochaines fois
                                state["db_task_id"] = task_id_int
                            else:
                                logger.error(f"❌ Aucune tâche trouvée pour monday_item_id={monday_item_id}")
                    except Exception as e:
                        logger.error(f"❌ Erreur récupération task_id depuis DB: {e}")
                        
            if not task_id_int:
                logger.error(f"❌ Impossible de déterminer task_id - skip sauvegarde validation en DB")
                # Ne pas bloquer le workflow, continuer sans sauvegarder en DB
                task_id_int = None  # On continuera sans sauvegarder
            
            task_run_id_int = state.get("db_run_id")
            # ✅ CORRECTION: Récupérer current_step_id depuis le state, pas depuis results
            # Le decorator persistence_decorator stocke current_step_id directement dans state
            run_step_id = state.get("current_step_id") or state.get("db_step_id")
            
            # ✅ CORRECTION: Ne sauvegarder en DB que si task_id_int est valide
            if task_id_int:
                success = await human_validation_service.create_validation_request(
                    validation_request=validation_request,
                    task_id=task_id_int,
                    task_run_id=task_run_id_int,
                    run_step_id=run_step_id
                )
                
                if success:
                    logger.info(f"✅ Validation {validation_id} créée en base de données")
                    state["results"]["validation_id"] = validation_id
                    workflow_results["validation_id"] = validation_id  # ✅ NOUVEAU: Ajouter aux workflow_results
                    state["results"]["ai_messages"].append(f"✅ Validation {validation_id} sauvegardée en DB")
                else:
                    logger.warning(f"⚠️ Échec sauvegarde validation {validation_id} en DB - continuation du workflow")
            else:
                logger.warning(f"⚠️ task_id manquant - skip sauvegarde validation en DB, workflow continue")
                
        except Exception as db_error:
            logger.error(f"❌ Erreur lors de la création de validation en DB: {db_error}")
            state["results"]["ai_messages"].append(f"⚠️ Erreur DB validation: {str(db_error)}")
        
        # 3. Poster l'update de validation dans Monday.com
        # ✅ CORRECTION: Utiliser monday_item_id au lieu de task_id pour les appels Monday.com
        monday_item_id = str(state["task"].monday_item_id) if state["task"].monday_item_id else state["task"].task_id
        logger.info(f"📝 Posting update de validation pour item Monday.com {monday_item_id}")
        
        try:
            update_id = await monday_validation_service.post_validation_update(
                item_id=monday_item_id,
                workflow_results=workflow_results
            )
            
            # ✅ PROTECTION SUPPLÉMENTAIRE: Vérifier le type de retour
            if not isinstance(update_id, str):
                logger.error(f"❌ Update ID invalide (type {type(update_id)}): {update_id}")
                raise Exception(f"Update ID invalide: attendu str, reçu {type(update_id)}")
                
        except Exception as post_error:
            logger.error(f"❌ Erreur lors du post validation update: {str(post_error)}")
            # En cas d'erreur, continuer avec un update_id par défaut
            update_id = f"failed_update_{monday_item_id}"
            state["results"]["validation_error"] = str(post_error)
            state["results"]["ai_messages"].append(f"❌ Erreur validation Monday.com: {str(post_error)}")
        
        state["results"]["validation_update_id"] = update_id
        state["results"]["ai_messages"].append(f"✅ Update de validation postée: {update_id}")
        
        # 4. Tracer avec LangSmith
        if langsmith_config.client:
            try:
                # ✅ COHÉRENCE: Utiliser monday_item_id pour l'affichage
                display_item_id = str(state["task"].monday_item_id) if hasattr(state["task"], 'monday_item_id') and state["task"].monday_item_id else str(state["task"].task_id)
                
                langsmith_config.client.create_run(
                    name="monday_validation_update_posted",
                    run_type="tool",
                    inputs={
                        "item_id": display_item_id,  # Monday item ID
                        "task_title": state["task"].title,
                        "update_id": update_id,
                        "workflow_results": workflow_results
                    },
                    outputs={
                        "status": "waiting_for_human_reply",
                        "update_posted": True
                    },
                    session_name=state.get("langsmith_session"),
                    extra={
                        "workflow_id": state.get("workflow_id"),
                        "monday_validation": True
                    }
                )
            except Exception as e:
                logger.warning(f"⚠️ Erreur LangSmith tracing: {e}")
        
        # 5. Attendre la réponse humaine
        logger.info(f"⏳ Attente de reply humaine sur update {update_id}...")
        state["results"]["ai_messages"].append("⏳ En attente de reply humaine dans Monday.com...")
        
        # ✅ CORRECTION: Réduire le timeout pour éviter les blocages
        # Attendre la réponse (avec timeout réduit de 60 min à 10 min)
        validation_response = await monday_validation_service.check_for_human_replies(
            update_id=update_id,
            timeout_minutes=10  # ✅ CORRECTION: Timeout réduit de 60 à 10 minutes
        )
        
        # ✅ NOUVEAU: Gestion intelligente du timeout de validation
        if validation_response is None:
            logger.warning("⏰ Timeout validation Monday.com - Application mode automatique")
            
            # Analyser les résultats pour prendre une décision automatique
            results = state.get("results", {})
            
            # Critères pour approuver automatiquement:
            # 1. Tests passent (si exécutés)
            # 2. Pas d'erreur critique
            # 3. Au moins un fichier modifié
            
            has_tests_success = results.get("test_results", {}).get("success", True)
            has_critical_error = len(results.get("error_logs", [])) > 0
            has_modified_files = len(results.get("modified_files", [])) > 0
            
            auto_approve = (
                has_tests_success and 
                not has_critical_error and 
                has_modified_files
            )
            
            if auto_approve:
                logger.info("✅ Validation automatique approuvée (critères remplis)")
                state["results"]["monday_validation"] = {
                    "human_decision": "approve_auto",
                    "timeout": True,
                    "auto_approved": True,
                    "reason": "Tests passent, pas d'erreur critique, fichiers modifiés"
                }
                state["results"]["ai_messages"].append("✅ Validation automatique: Critères de qualité remplis")
            else:
                logger.warning("⚠️ Validation automatique rejetée (critères non remplis)")
                state["results"]["monday_validation"] = {
                    "human_decision": "timeout", 
                    "timeout": True,
                    "auto_approved": False,
                    "reason": f"Tests: {has_tests_success}, Erreurs: {has_critical_error}, Fichiers: {has_modified_files}"
                }
                state["results"]["ai_messages"].append("⚠️ Validation expirée - update Monday.com seulement")
        else:
            # 6. Traiter la réponse de validation et sauvegarder en DB
            state["results"]["validation_response"] = validation_response
            
            # ✅ CORRECTION: Gérer les différents formats de status (string vs enum)
            status_value = validation_response.status.value if hasattr(validation_response.status, 'value') else str(validation_response.status)
            state["results"]["human_validation_status"] = status_value
            
            logger.info(f"📊 Statut de validation reçu: '{status_value}' (type: {type(validation_response.status)})")
            
            # ✅ AMÉLIORATION: Mapper tous les cas possibles de statut
            if status_value in ["approve", "approved", "APPROVED"]:
                logger.info("✅ Code approuvé par l'humain via Monday.com")
                state["results"]["ai_messages"].append("✅ Code approuvé - Préparation du merge...")
                state["results"]["should_merge"] = True
                state["results"]["human_decision"] = "approved"
                
            elif status_value in ["reject", "rejected", "REJECTED", "debug"]:
                logger.info("🔧 Debug demandé par l'humain via Monday.com")
                state["results"]["ai_messages"].append(f"🔧 Debug demandé: {validation_response.comments}")
                state["results"]["should_merge"] = False
                state["results"]["human_decision"] = "rejected"
                state["results"]["debug_request"] = validation_response.comments
                
            elif status_value in ["expired", "EXPIRED", "timeout"]:
                logger.warning("⏰ Validation expirée - timeout atteint")
                state["results"]["ai_messages"].append("⏰ Validation expirée - update Monday.com seulement")
                state["results"]["should_merge"] = False
                state["results"]["human_decision"] = "timeout"
                
            else:
                logger.warning(f"⚠️ Statut de validation inconnu: {status_value}")
                state["results"]["ai_messages"].append(f"⚠️ Statut inconnu: {status_value} - Workflow arrêté")
                state["results"]["should_merge"] = False
                state["results"]["human_decision"] = "error"
            
            # 7. Sauvegarder la réponse de validation en base de données
            try:
                # ✅ CORRECTION ERREUR 2: Utiliser le validation_id DB stocké dans le state, pas celui de Monday
                db_validation_id = state.get("results", {}).get("validation_id")
                
                if not db_validation_id:
                    logger.info("ℹ️ Pas de validation_id en DB - la validation n'a pas été sauvegardée initialement, skip sauvegarde réponse")
                    # Ce n'est pas une erreur - cela arrive quand task_id_int était None
                elif validation_response:
                    # Initialiser le service si nécessaire
                    if not human_validation_service.db_pool:
                        await human_validation_service.init_db_pool()
                    
                    # ✅ CORRECTION: Créer une copie de la réponse avec le bon validation_id DB
                    # validation_response.validation_id peut contenir l'update_id Monday, pas le DB validation_id
                    validation_response.validation_id = db_validation_id
                    
                    # Sauvegarder la réponse
                    response_saved = await human_validation_service.submit_validation_response(
                        validation_id=db_validation_id,
                        response=validation_response
                    )
                    
                    if response_saved:
                        logger.info(f"✅ Réponse validation {db_validation_id} sauvegardée en DB")
                        state["results"]["ai_messages"].append("✅ Réponse validation sauvegardée en DB")
                    else:
                        logger.warning(f"⚠️ Échec sauvegarde réponse validation en DB")
                else:
                    logger.warning("⚠️ Aucune réponse de validation à sauvegarder")
                        
            except Exception as db_error:
                logger.error(f"❌ Erreur sauvegarde réponse validation en DB: {db_error}")
                # Ne pas bloquer le workflow pour une erreur de persistence
                state["results"]["ai_messages"].append(f"⚠️ Erreur DB réponse: {str(db_error)}")
                
        # 8. Tracer la réponse finale
        if langsmith_config.client and validation_response:
            try:
                langsmith_config.client.create_run(
                    name="monday_validation_response_received",
                    run_type="tool",
                    inputs={
                        "update_id": update_id,
                        "response_status": validation_response.status.value,
                        "human_comments": validation_response.comments
                    },
                    outputs={
                        "should_merge": state["results"].get("should_merge", False),
                        "human_decision": state["results"].get("human_decision", "error")
                    },
                    session_name=state.get("langsmith_session"),
                    extra={
                        "workflow_id": state.get("workflow_id"),
                        "monday_validation": True,
                        "validated_by": validation_response.validated_by
                    }
                )
            except Exception as e:
                logger.warning(f"⚠️ Erreur LangSmith tracing: {e}")
        
        logger.info(f"🤝 Validation Monday.com terminée: {state['results'].get('human_decision', 'error')}")
        
    except Exception as e:
        error_msg = f"Erreur validation Monday.com: {str(e)}"
        logger.error(f"❌ {error_msg}")
        state["results"]["error_logs"].append(error_msg)
        state["results"]["ai_messages"].append(f"❌ {error_msg}")
        state["results"]["should_merge"] = False
        state["results"]["human_decision"] = "error"
    
    return state


def _prepare_workflow_results(state: GraphState) -> Dict[str, Any]:
    """Prépare les résultats du workflow pour l'update de validation."""
    
    task = state["task"]
    results = state.get("results", {})
    
    # Déterminer le niveau de succès
    success_level = "unknown"
    if results.get("test_results"):
        test_results = results["test_results"]
        # test_results est une liste de résultats de test
        if isinstance(test_results, list) and test_results:
            # Prendre le dernier résultat de test
            last_test = test_results[-1]
            # Gérer à la fois les dictionnaires et les objets TestResult
            if isinstance(last_test, dict):
                success_level = "success" if last_test.get("success") else "partial"
            elif hasattr(last_test, 'success'):
                # C'est un objet TestResult
                success_level = "success" if last_test.success else "partial"
            else:
                success_level = "partial"
        elif isinstance(test_results, dict):
            success_level = "success" if test_results.get("success") else "partial"
        elif hasattr(test_results, 'success'):
            # C'est un objet TestResult
            success_level = "success" if test_results.success else "partial"
        else:
            success_level = "partial"
    elif results.get("error_logs") and len(results["error_logs"]) > 0:
        success_level = "failed"
    else:
        success_level = "partial"
    
    # Récupérer l'URL de la PR
    pr_url = None
    if results.get("pr_info"):
        pr_info = results["pr_info"]
        if isinstance(pr_info, dict):
            pr_url = pr_info.get("pr_url") or pr_info.get("url")
        else:
            pr_url = getattr(pr_info, "url", None) or getattr(pr_info, "pr_url", None)
    
    # ✅ ROBUSTESSE: Analyser et valider tous les aspects du workflow
    workflow_analysis = _analyze_workflow_completion(state, task, results, pr_url)
    
    # Préparer les résultats formatés avec validation complète
    workflow_results = {
        # ✅ INFORMATIONS DE BASE
        "task_title": task.title,
        "task_id": task.task_id,
        "success_level": success_level,
        "workflow_id": state.get("workflow_id"),
        
        # ✅ RÉSULTATS TECHNIQUES VALIDÉS
        "environment_path": workflow_analysis["environment"]["path"],
        "environment_valid": workflow_analysis["environment"]["is_valid"],
        "modified_files": workflow_analysis["implementation"]["modified_files"],
        "implementation_success": workflow_analysis["implementation"]["success"],
        "implementation_details": workflow_analysis["implementation"]["details"],
        
        # ✅ TESTS AVEC ANALYSE DÉTAILLÉE
        "test_executed": workflow_analysis["testing"]["executed"],
        "test_success": workflow_analysis["testing"]["success"],
        "test_results": workflow_analysis["testing"]["results"],
        "test_summary": workflow_analysis["testing"]["summary"],
        
        # ✅ PULL REQUEST AVEC VALIDATION
        "pr_created": workflow_analysis["pr"]["created"],
        "pr_url": workflow_analysis["pr"]["url"],
        "pr_status": workflow_analysis["pr"]["status"],
        
        # ✅ MÉTRIQUES ET MONITORING
        "workflow_metrics": workflow_analysis["metrics"],
        "error_logs": results.get("error_logs", []),
        "error_summary": workflow_analysis["errors"]["summary"],
        "ai_messages": results.get("ai_messages", []),
        
        # ✅ CONTEXTE TEMPOREL ET TRAÇABILITÉ
        "duration_info": workflow_analysis["duration"],
        "completed_nodes": state.get("completed_nodes", []),
        "workflow_stage": results.get("workflow_stage", "unknown"),
        
        # ✅ VALIDATION GLOBALE
        "overall_success": workflow_analysis["overall"]["success"],
        "completion_score": workflow_analysis["overall"]["score"],
        "recommendations": workflow_analysis["overall"]["recommendations"]
    }
    
    return workflow_results


def _analyze_workflow_completion(state: Dict[str, Any], task: Any, results: Dict[str, Any], pr_url: Optional[str]) -> Dict[str, Any]:
    """
    Analyse complète et robuste de l'état d'achèvement du workflow.
    
    Cette fonction effectue une validation approfondie de tous les aspects du workflow
    pour générer des métriques fiables et des recommandations.
    
    Args:
        state: État complet du workflow
        task: Objet tâche
        results: Résultats du workflow
        pr_url: URL de la pull request si créée
        
    Returns:
        Analyse structurée avec toutes les métriques et validations
    """
    from datetime import datetime
    
    analysis = {
        "environment": {},
        "implementation": {},
        "testing": {},
        "pr": {},
        "metrics": {},
        "errors": {},
        "duration": {},
        "overall": {}
    }
    
    try:
        # ✅ ANALYSE ENVIRONNEMENT
        working_dir = state.get("working_directory") or results.get("working_directory")
        analysis["environment"] = {
            "path": working_dir if working_dir != "Non disponible" else None,
            "is_valid": bool(working_dir and working_dir != "Non disponible"),
            "source": "state" if state.get("working_directory") else "results" if results.get("working_directory") else "none"
        }
        
        # ✅ ANALYSE IMPLÉMENTATION DÉTAILLÉE
        modified_files = results.get("modified_files", [])
        code_changes = results.get("code_changes", {})
        impl_success = results.get("implementation_success", False)
        impl_metrics = results.get("implementation_metrics", {})
        
        analysis["implementation"] = {
            "success": impl_success,
            "modified_files": modified_files,
            "files_count": len(modified_files),
            "code_changes_count": len(code_changes),
            "details": {
                "has_code_changes": len(code_changes) > 0,
                "has_modified_files": len(modified_files) > 0,
                "metrics": impl_metrics,
                "consistency_check": _validate_implementation_consistency(modified_files, code_changes, impl_success)
            }
        }
        
        # ✅ ANALYSE TESTS SOPHISTIQUÉE
        test_results = results.get("test_results", [])
        test_success = results.get("test_success", False)
        
        analysis["testing"] = _analyze_testing_results(test_results, test_success, results)
        
        # ✅ ANALYSE PULL REQUEST
        analysis["pr"] = {
            "created": bool(pr_url),
            "url": pr_url,
            "status": "created" if pr_url else "not_created",
            "validation": _validate_pr_creation(pr_url, impl_success, modified_files)
        }
        
        # ✅ CALCUL MÉTRIQUES AVANCÉES
        analysis["metrics"] = _calculate_workflow_metrics(state, results)
        
        # ✅ ANALYSE ERREURS STRUCTURÉE
        error_logs = results.get("error_logs", [])
        analysis["errors"] = {
            "count": len(error_logs),
            "has_errors": len(error_logs) > 0,
            "summary": _categorize_errors(error_logs),
            "critical_errors": [err for err in error_logs if "critique" in err.lower() or "critical" in err.lower()]
        }
        
        # ✅ CALCUL DURÉE ET CONTEXTE TEMPOREL
        analysis["duration"] = _calculate_duration_info(state)
        
        # ✅ ÉVALUATION GLOBALE SOPHISTIQUÉE
        analysis["overall"] = _calculate_overall_success(analysis, impl_success, test_success)
        
    except Exception as e:
        logger.error(f"❌ Erreur analyse workflow completion: {e}")
        # Fallback vers une analyse minimale
        analysis = _create_fallback_analysis(state, results, pr_url, str(e))
    
    return analysis


def _validate_implementation_consistency(modified_files: list, code_changes: dict, impl_success: bool) -> Dict[str, Any]:
    """Valide la cohérence entre les différents indicateurs d'implémentation."""
    return {
        "files_vs_changes_consistent": len(modified_files) == len(code_changes),
        "success_vs_changes_consistent": impl_success == (len(modified_files) > 0 or len(code_changes) > 0),
        "has_actual_work": len(modified_files) > 0 or len(code_changes) > 0,
        "potential_issues": []
    }


def _analyze_testing_results(test_results: list, test_success: bool, results: Dict[str, Any]) -> Dict[str, Any]:
    """Analyse sophistiquée des résultats de tests."""
    return {
        "executed": len(test_results) > 0 or bool(results.get("test_executed")),
        "success": test_success,
        "results": test_results,
        "count": len(test_results),
        "summary": f"{len(test_results)} test(s) exécuté(s)" if test_results else "Aucun test exécuté",
        "details": {
            "has_results": len(test_results) > 0,
            "success_rate": _calculate_test_success_rate(test_results),
            "test_types": _identify_test_types(test_results)
        }
    }


def _validate_pr_creation(pr_url: Optional[str], impl_success: bool, modified_files: list) -> Dict[str, Any]:
    """Valide la logique de création de PR."""
    return {
        "should_have_pr": impl_success and len(modified_files) > 0,
        "has_pr": bool(pr_url),
        "consistent": bool(pr_url) == (impl_success and len(modified_files) > 0),
        "recommendation": "PR expected" if (impl_success and len(modified_files) > 0) else "No PR needed"
    }


def _calculate_workflow_metrics(state: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
    """Calcule des métriques avancées sur le workflow."""
    return {
        "workflow_id": state.get("workflow_id", "unknown"),
        "nodes_completed": len(state.get("completed_nodes", [])),
        "ai_messages_count": len(results.get("ai_messages", [])),
        "workflow_stage": results.get("workflow_stage", "unknown"),
        "has_monitoring": bool(state.get("monitoring_enabled")),
        "execution_environment": "production" if "prod" in str(state.get("workflow_id", "")).lower() else "development"
    }


def _categorize_errors(error_logs: list) -> Dict[str, Any]:
    """Catégorise les erreurs par type et gravité."""
    if not error_logs:
        return {"categories": {}, "severity": "none", "total": 0}
    
    categories = {
        "critical": len([e for e in error_logs if "critique" in e.lower() or "critical" in e.lower()]),
        "database": len([e for e in error_logs if "database" in e.lower() or "db" in e.lower()]),
        "network": len([e for e in error_logs if "network" in e.lower() or "connection" in e.lower()]),
        "validation": len([e for e in error_logs if "validation" in e.lower() or "invalid" in e.lower()]),
        "other": 0
    }
    
    categories["other"] = len(error_logs) - sum(categories.values())
    
    severity = "critical" if categories["critical"] > 0 else "warning" if len(error_logs) > 0 else "none"
    
    return {
        "categories": categories,
        "severity": severity,
        "total": len(error_logs),
        "most_recent": error_logs[-1] if error_logs else None
    }


def _calculate_duration_info(state: Dict[str, Any]) -> Dict[str, Any]:
    """Calcule les informations de durée du workflow."""
    from datetime import datetime
    
    started_at = state.get("started_at")
    current_time = state.get("current_time") or datetime.now().isoformat()
    
    duration_info = {
        "started_at": started_at,
        "current_time": current_time,
        "duration_seconds": None,
        "duration_human": None
    }
    
    if started_at:
        try:
            from dateutil.parser import parse
            start_dt = parse(started_at)
            current_dt = parse(current_time) if isinstance(current_time, str) else datetime.now()
            duration = current_dt - start_dt
            
            duration_info["duration_seconds"] = duration.total_seconds()
            duration_info["duration_human"] = str(duration).split('.')[0]  # Sans microsecondes
        except Exception:
            pass
    
    return duration_info


def _calculate_overall_success(analysis: Dict[str, Any], impl_success: bool, test_success: bool) -> Dict[str, Any]:
    """Calcule le succès global avec score et recommandations."""
    score = 0
    recommendations = []
    
    # Score environnement (20 points)
    if analysis["environment"]["is_valid"]:
        score += 20
    else:
        recommendations.append("Vérifier la configuration d'environnement")
    
    # Score implémentation (40 points)
    if impl_success and analysis["implementation"]["files_count"] > 0:
        score += 40
    elif impl_success:
        score += 20
        recommendations.append("Implémentation réussie mais aucun fichier modifié")
    else:
        recommendations.append("Revoir l'implémentation qui a échoué")
    
    # Score tests (20 points)
    if analysis["testing"]["executed"]:
        if test_success:
            score += 20
        else:
            score += 10
            recommendations.append("Corriger les tests qui ont échoué")
    else:
        recommendations.append("Ajouter des tests pour valider l'implémentation")
    
    # Score PR (20 points)
    if analysis["pr"]["created"]:
        score += 20
    elif analysis["pr"]["validation"]["should_have_pr"]:
        recommendations.append("Créer une Pull Request pour les modifications")
    else:
        score += 10  # Pas de PR nécessaire
    
    # Bonus/malus erreurs
    error_count = analysis["errors"]["count"]
    if error_count == 0:
        score += 5
    elif error_count > 5:
        score -= 10
        recommendations.append("Réduire le nombre d'erreurs dans le workflow")
    
    return {
        "success": score >= 80,
        "score": min(100, max(0, score)),  # Entre 0 et 100
        "grade": _get_grade_from_score(score),
        "recommendations": recommendations[:3]  # Top 3 recommendations
    }


def _get_grade_from_score(score: int) -> str:
    """Convertit un score numérique en grade lisible."""
    if score >= 90:
        return "Excellent"
    elif score >= 80:
        return "Bon"
    elif score >= 60:
        return "Acceptable"
    elif score >= 40:
        return "Insuffisant"
    else:
        return "Échec"


def _calculate_test_success_rate(test_results: list) -> float:
    """Calcule le taux de succès des tests."""
    if not test_results:
        return 0.0
    
    successful_tests = 0
    for result in test_results:
        if isinstance(result, dict):
            if result.get("success", False) or result.get("passed", False):
                successful_tests += 1
        elif isinstance(result, str) and "success" in result.lower():
            successful_tests += 1
    
    return successful_tests / len(test_results)


def _identify_test_types(test_results: list) -> list:
    """Identifie les types de tests exécutés."""
    test_types = set()
    for result in test_results:
        if isinstance(result, dict):
            test_type = result.get("type", "unknown")
            test_types.add(test_type)
        elif isinstance(result, str):
            if "unit" in result.lower():
                test_types.add("unit")
            elif "integration" in result.lower():
                test_types.add("integration")
            else:
                test_types.add("unknown")
    
    return list(test_types)


def _create_fallback_analysis(state: Dict[str, Any], results: Dict[str, Any], pr_url: Optional[str], error: str) -> Dict[str, Any]:
    """Crée une analyse minimale en cas d'erreur."""
    return {
        "environment": {"path": "Non disponible", "is_valid": False},
        "implementation": {"success": False, "modified_files": [], "files_count": 0, "details": {}},
        "testing": {"executed": False, "success": False, "results": [], "summary": "Analyse impossible"},
        "pr": {"created": bool(pr_url), "url": pr_url, "status": "unknown"},
        "metrics": {"error": error},
        "errors": {"count": 1, "summary": {"severity": "critical", "total": 1}},
        "duration": {"started_at": None, "current_time": None},
        "overall": {"success": False, "score": 0, "grade": "Erreur", "recommendations": ["Corriger l'erreur d'analyse"]}
    } 