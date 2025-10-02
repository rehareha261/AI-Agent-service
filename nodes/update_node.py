"""Nœud de mise à jour Monday - met à jour le ticket avec les résultats."""

from datetime import datetime
from models.schemas import WorkflowStatus  
from models.state import GraphState
from tools.monday_tool import MondayTool
from utils.logger import get_logger
from utils.helpers import ensure_state_structure, add_ai_message, add_error_log

logger = get_logger(__name__)


async def update_monday(state: GraphState) -> GraphState:
    """
    Nœud de mise à jour Monday.com : met à jour l'item avec les résultats finaux.
    
    Ce nœud :
    1. Collecte tous les résultats du workflow
    2. Génère un commentaire de completion
    3. Met à jour le statut de l'item Monday.com
    4. Attache les liens vers la PR et les artefacts
    5. Marque la tâche comme terminée
    
    Args:
        state: État actuel du graphe
        
    Returns:
        État mis à jour avec le statut final
    """
    logger.info(f"📝 Mise à jour Monday.com pour: {state['task'].title}")
    
    # ✅ CORRECTION CRITIQUE: Assurer l'intégrité de l'état dès le début
    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)

    # Initialiser structures si nécessaire
    if "results" not in state:
        state["results"] = {}
    
    if "ai_messages" not in state["results"]:
        state["results"]["ai_messages"] = []
    
    state["results"]["ai_messages"].append("📋 Début de la mise à jour du ticket Monday.com...")
    
    try:
        # Initialiser l'outil Monday
        monday_tool = MondayTool()
        
        # ✅ CORRECTION: Vérifier la configuration Monday.com avant toute opération
        if not hasattr(monday_tool, 'api_token') or not monday_tool.api_token:
            logger.info("💡 Monday.com non configuré - mise à jour ignorée")
            # Marquer le workflow comme complété même sans Monday.com
            state["status"] = "completed"
            if "results" not in state:
                state["results"] = {}
            state["results"]["monday_update_skipped"] = "Configuration Monday.com manquante"
            return state
        
        task = state["task"]
        
        # 1. Déterminer le statut final
        final_status, success_level = _determine_final_status(state)
        
        # 2. Générer le commentaire de completion
        completion_comment = await _generate_completion_comment(state, success_level)
        
        # 3. Récupérer l'URL de la PR si disponible dans les résultats
        pr_url = None
        if state["results"] and "pr_info" in state["results"]:
            pr_info = state["results"]["pr_info"]
            pr_url = pr_info.get("pr_url") if isinstance(pr_info, dict) else getattr(pr_info, "pr_url", None)
        
        logger.info(f"📝 Mise à jour statut: {final_status}, PR: {pr_url or 'N/A'}")
        
        # 4. Exécuter la mise à jour complète
        if success_level == "success":
            # Tâche complètement réussie
            update_result = await monday_tool._arun(
                action="complete_task",
                item_id=task.task_id,
                pr_url=pr_url,
                completion_comment=completion_comment
            )
            
            # ✅ PROTECTION: S'assurer que le résultat est un dictionnaire
            if not isinstance(update_result, dict):
                logger.error(f"❌ update_result n'est pas un dictionnaire: {type(update_result)} - {update_result}")
                update_result = {"success": False, "error": f"Type invalide: {type(update_result)}"}
        else:
            # Tâche partiellement réussie ou échouée
            # Mettre à jour le statut manuellement
            status_result = await monday_tool._arun(
                action="update_item_status",
                item_id=task.task_id,
                status=final_status
            )
            
            # Ajouter le commentaire
            comment_result = await monday_tool._arun(
                action="add_comment",
                item_id=task.task_id,
                comment=completion_comment
            )
            
            # ✅ PROTECTION: S'assurer que les résultats sont des dictionnaires
            if not isinstance(status_result, dict):
                logger.error(f"❌ status_result n'est pas un dictionnaire: {type(status_result)} - {status_result}")
                if isinstance(status_result, list):
                    status_result = {"success": False, "error": f"API retourné liste: {status_result}"}
                else:
                    status_result = {"success": False, "error": f"Type invalide: {type(status_result)}"}
            
            if not isinstance(comment_result, dict):
                logger.error(f"❌ comment_result n'est pas un dictionnaire: {type(comment_result)} - {comment_result}")
                if isinstance(comment_result, list):
                    comment_result = {"success": False, "error": f"API retourné liste: {comment_result}"}
                else:
                    comment_result = {"success": False, "error": f"Type invalide: {type(comment_result)}"}
            
            update_result = {
                "success": status_result.get("success", False) and comment_result.get("success", False),
                "operations": [("status", status_result), ("comment", comment_result)]
            }
        
        # 5. Traiter le résultat de la mise à jour
        if update_result.get("success", False):
            logger.info("✅ Monday.com mis à jour avec succès")
            
            # ✅ AJOUT: Messages informatifs pour l'affichage du workflow
            update_summary = f"✅ Mise à jour Monday.com réussie - Statut: {final_status}"
            if pr_url:
                update_summary += f" | PR: {pr_url}"
            
            state["results"]["ai_messages"].append(update_summary)
            state["results"]["ai_messages"].append("📋 Ticket Monday.com mis à jour avec les résultats du workflow")
            
            # Mettre à jour l'état final
            state["status"] = WorkflowStatus.COMPLETED
            state["completed_at"] = datetime.now()
            
            # Stocker les résultats de la mise à jour dans results
            state["results"]["monday_update"] = {
                "success": True,
                "message": "Monday.com mis à jour avec succès",
                "final_status": final_status,
                "pr_url": pr_url,
                "comment_added": True
            }
        else:
            error_msg = update_result.get("error", "Erreur inconnue lors de la mise à jour Monday")
            logger.error(f"❌ Échec mise à jour Monday.com: {error_msg}")
            
            # ✅ AJOUT: Messages d'erreur pour l'affichage du workflow
            state["results"]["ai_messages"].append(f"❌ Échec mise à jour Monday.com: {error_msg}")
            state["results"]["ai_messages"].append("⚠️ Le workflow a été complété mais la mise à jour du ticket a échoué")
            
            state["status"] = WorkflowStatus.FAILED
            state["error"] = f"Échec mise à jour Monday: {error_msg}"
            
            # Stocker les résultats d'erreur dans results
            state["results"]["monday_update"] = {
                "success": False,
                "error": error_msg,
                "final_status": "Échec mise à jour",
                "comment_added": False
            }
            
    except Exception as e:
        error_msg = f"Exception lors de la mise à jour Monday: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # ✅ AJOUT: Messages d'exception pour l'affichage du workflow
        state["results"]["ai_messages"].append(f"❌ Exception lors de la mise à jour Monday.com: {str(e)}")
        state["results"]["ai_messages"].append("⚠️ Erreur technique lors de la mise à jour du ticket")
        
        state["status"] = WorkflowStatus.FAILED
        state["error"] = error_msg
        
        # Stocker les résultats d'exception dans results
        state["results"]["monday_update"] = {
            "success": False, 
            "error": error_msg,
            "final_status": "Erreur technique",
            "comment_added": False
        }
    
    # ✅ CORRECTION: Retourner l'état complet au lieu d'un dictionnaire
    return state


def _determine_final_status(state: GraphState) -> tuple[str, str]:
    """
    Détermine le statut final de la tâche basé sur les résultats.
    
    Returns:
        Tuple (statut_monday, niveau_succès)
    """
    # Vérifier le statut du workflow avec protection
    current_status = getattr(state, 'status', WorkflowStatus.PENDING)
    
    if current_status == WorkflowStatus.COMPLETED:
        # Vérifier si on a une PR
        if state["results"] and "pr_info" in state["results"]:
            return "Terminé", "success"
        else:
            return "En attente", "partial"
    elif current_status == WorkflowStatus.FAILED:
        # Analyser les erreurs pour déterminer le type d'échec
        if state["error"] and any(keyword in state["error"].lower() for keyword in ["git", "clone", "repository"]):
            return "Bloqué - Repository", "failed"
        elif state["error"] and any(keyword in state["error"].lower() for keyword in ["test", "tests"]):
            return "Échec Tests", "failed"
        else:
            return "Bloqué", "failed"
    else:
        # Workflow en cours ou annulé
        return "En cours", "partial"


async def _generate_completion_comment(state: GraphState, success_level: str) -> str:
    """
    Génère le commentaire de completion pour Monday.com.
    """
    task = state["task"]
    
    # En-tête basé sur le niveau de succès
    if success_level == "success":
        header = "✅ **Tâche Complétée avec Succès**\n\n"
    elif success_level == "partial":
        header = "⚠️ **Tâche Partiellement Complétée**\n\n"
    else:
        header = "❌ **Tâche Échouée**\n\n"
    
    # Informations de base
    basic_info = f"**Tâche**: {task.title}\n"
    basic_info += f"**Type**: {task.task_type}\n"
    basic_info += f"**Priorité**: {task.priority}\n\n"
    
    # Résultats détaillés
    results_section = "## 📊 Résultats\n\n"
    
    # Informations sur le workflow
    if state["completed_at"] and state["started_at"]:
        duration = (state["completed_at"] - state["started_at"]).total_seconds()
        results_section += f"- **Durée**: {duration:.1f} secondes\n"
    
    # Statut final
    final_status = getattr(state, 'status', 'Inconnu')
    results_section += f"- **Statut Final**: {final_status}\n"
    
    # Nœuds complétés
    if state["completed_nodes"]:
        results_section += f"- **Étapes Complétées**: {', '.join(state["completed_nodes"])}\n"
    
    # Informations sur la PR
    pr_section = ""
    if state["results"] and "pr_info" in state["results"]:
        pr_info = state["results"]["pr_info"]
        pr_section = "\n## 🔗 Pull Request\n\n"
        if isinstance(pr_info, dict):
            pr_section += f"- **URL**: {pr_info.get('pr_url', 'N/A')}\n"
            pr_section += f"- **Branche**: {pr_info.get('branch', 'N/A')}\n"
    
    # Section d'erreur si applicable
    error_section = ""
    if state["error"]:
        error_section = f"\n## ❌ Erreurs\n\n```\n{state["error"]}\n```\n"
    
    # Métriques additionnelles
    metrics_section = "\n## 📈 Métriques\n\n"
    if state["results"]:
        for key, value in state["results"].items():
            if key not in ["pr_info"] and isinstance(value, (str, int, float)):
                metrics_section += f"- **{key.replace('_', ' ').title()}**: {value}\n"
    
    # Assemblage final
    comment = header + basic_info + results_section + pr_section + error_section + metrics_section
    
    # Footer avec timestamp
    comment += f"\n---\n*Mis à jour automatiquement par AI-Agent le {datetime.now().strftime('%d/%m/%Y à %H:%M')}*"
    
    return comment 