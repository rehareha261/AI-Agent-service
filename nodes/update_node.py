"""Nœud de mise à jour Monday - met à jour le ticket avec les résultats."""

from datetime import datetime
from models.schemas import WorkflowStatus
from models.state import GraphState
from tools.monday_tool import MondayTool
from services.github_pr_service import github_pr_service
from utils.logger import get_logger
# from utils.helpers import ensure_state_structure, add_ai_message, add_error_log  # Non utilisé

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

        # ✅ VALIDATION CRITIQUE: Vérifier cohérence merge_successful vs final_status
        if state["results"].get("merge_successful", False) and final_status != "Done":
            logger.error(f"❌ INCOHÉRENCE: merge_successful=True mais final_status='{final_status}'")
            logger.warning("🔧 Correction automatique - Forçage à 'Done'")
            final_status = "Done"
            success_level = "success"
            state["results"]["status_corrected"] = True

        # 2. Générer le commentaire de completion
        completion_comment = await _generate_completion_comment(state, success_level)

        # ✅ ENRICHISSEMENT: Ajouter info de merge dans le commentaire si disponible
        if state["results"].get("merge_successful", False):
            merge_info = "\n\n✅ **Pull Request mergée avec succès**\n"
            if state["results"].get("merge_commit"):
                merge_info += f"- **Commit de merge**: `{state['results']['merge_commit']}`\n"
            if state["results"].get("merge_commit_url"):
                merge_info += f"- **Lien**: {state['results']['merge_commit_url']}\n"
            completion_comment += merge_info

        # 3. Récupérer l'URL de la PR si disponible dans les résultats
        pr_url = None
        if state["results"] and "pr_info" in state["results"]:
            pr_info = state["results"]["pr_info"]
            pr_url = pr_info.get("pr_url") if isinstance(pr_info, dict) else getattr(pr_info, "pr_url", None)

        logger.info(f"📝 Mise à jour statut: {final_status}, PR: {pr_url or 'N/A'}")

        # ✅ CORRECTION: Utiliser monday_item_id pour les appels Monday.com API
        monday_item_id = str(task.monday_item_id) if task.monday_item_id else task.task_id

        # 4. Exécuter la mise à jour complète
        # ✅ AMÉLIORATION: Toujours mettre à jour le statut explicitement au lieu d'utiliser complete_task
        # Mettre à jour le statut avec le statut déterminé
        status_result = await monday_tool._arun(
            action="update_item_status",
            item_id=monday_item_id,
            status=final_status
        )

        # Ajouter le commentaire
        comment_result = await monday_tool._arun(
            action="add_comment",
            item_id=monday_item_id,
            comment=completion_comment
        )

        # Si c'est un succès avec une PR, ajouter le lien PR
        if success_level == "success" and pr_url:
            try:
                # ✅ CORRECTION: Utiliser l'ID de colonne configuré au lieu de "lien_pr" codé en dur
                from config.settings import get_settings
                settings = get_settings()
                
                if settings.monday_repository_url_column_id:
                    await monday_tool._arun(
                        action="update_column_value",
                        item_id=monday_item_id,
                        column_id=settings.monday_repository_url_column_id,
                        value=pr_url
                    )
                    logger.info(f"✅ Lien PR ajouté dans colonne {settings.monday_repository_url_column_id}: {pr_url}")
                else:
                    logger.warning("⚠️ Colonne Repository URL non configurée - lien PR non ajouté")
            except Exception as e:
                logger.debug(f"Impossible d'ajouter le lien PR (colonne peut-être absente): {e}")

        # ✅ NOUVEAU: Mettre à jour la colonne Repository URL avec la dernière PR fusionnée
        await _update_repository_url_column(state, monday_tool, monday_item_id)

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

            # ✅ VÉRIFICATION POST-UPDATE: Confirmer que le statut "Done" a bien été appliqué après merge
            if state["results"].get("merge_successful", False):
                if final_status != "Done":
                    logger.error(f"❌ ERREUR: Merge réussi mais statut='{final_status}'")
                    state["results"]["ai_messages"].append(
                        f"⚠️ Avertissement: Statut Monday='{final_status}' (attendu 'Done')"
                    )
                else:
                    logger.info("✅ Vérification: Statut 'Done' correctement appliqué")
                    state["results"]["ai_messages"].append(
                        "✅ Statut Monday.com mis à jour : Done"
                    )

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
    # ✅ PRIORITÉ ABSOLUE: Vérifier merge_successful EN PREMIER (avant toute autre vérification)
    if state["results"] and state["results"].get("merge_successful", False):
        logger.info("🎉 Merge réussi détecté - Statut forcé à 'Done'")
        return "Done", "success"

    # ✅ NOUVEAU: Vérifier d'abord si un statut explicite a été défini (ex: après merge)
    if state["results"] and "monday_final_status" in state["results"]:
        explicit_status = state["results"]["monday_final_status"]
        logger.info(f"📌 Utilisation du statut explicite: {explicit_status}")

        # Déterminer le niveau de succès basé sur le statut
        if explicit_status == "Done":
            return "Done", "success"
        elif explicit_status == "Working on it":
            return "Working on it", "partial"
        elif explicit_status == "Stuck":
            return "Stuck", "failed"
        else:
            return explicit_status, "partial"

    # Vérifier le statut du workflow avec protection
    current_status = getattr(state, 'status', WorkflowStatus.PENDING)

    if current_status == WorkflowStatus.COMPLETED:
        # Vérifier si on a une PR
        if state["results"] and "pr_info" in state["results"]:
            return "Working on it", "partial"  # PR créée mais pas encore mergée
        else:
            return "Working on it", "partial"
    elif current_status == WorkflowStatus.FAILED:
        # Analyser les erreurs pour déterminer le type d'échec
        if state["error"] and any(keyword in state["error"].lower() for keyword in ["git", "clone", "repository"]):
            return "Stuck", "failed"
        elif state["error"] and any(keyword in state["error"].lower() for keyword in ["test", "tests"]):
            return "Stuck", "failed"
        else:
            return "Stuck", "failed"
    else:
        # Workflow en cours ou annulé
        return "Working on it", "partial"


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

        # ✅ NOUVEAU: Ajouter les informations de merge si disponibles
        if state["results"].get("merge_successful", False):
            pr_section += "- **Statut**: ✅ Mergée avec succès\n"
            if state["results"].get("merge_commit"):
                pr_section += f"- **Commit de merge**: {state['results']['merge_commit']}\n"
            if state["results"].get("merge_commit_url"):
                pr_section += f"- **URL du commit**: {state['results']['merge_commit_url']}\n"
        elif "merge_successful" in state["results"]:
            pr_section += "- **Statut**: ⏳ En attente de validation/merge\n"

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


async def _update_repository_url_column(state: GraphState, monday_tool: MondayTool, monday_item_id: str) -> None:
    """
    Met à jour la colonne Repository URL avec l'URL de la dernière PR fusionnée.

    Cette fonction :
    1. Récupère l'URL du repository depuis l'état
    2. Récupère la dernière PR fusionnée sur ce repository
    3. Met à jour la colonne Repository URL dans Monday.com
    4. Sauvegarde l'URL en base de données

    Args:
        state: État du workflow
        monday_tool: Instance de l'outil Monday
        monday_item_id: ID de l'item Monday.com
    """
    try:
        # Vérifier si la colonne Repository URL est configurée
        from config.settings import get_settings
        settings = get_settings()

        if not settings.monday_repository_url_column_id:
            logger.debug("⏭️ Colonne Repository URL non configurée - mise à jour ignorée")
            return

        # Récupérer l'URL du repository depuis l'état
        repo_url = None
        if hasattr(state["task"], 'repository_url') and state["task"].repository_url:
            repo_url = state["task"].repository_url
        elif state["results"] and "repository_url" in state["results"]:
            repo_url = state["results"]["repository_url"]

        if not repo_url:
            logger.debug("⏭️ Aucune URL de repository trouvée - mise à jour Repository URL ignorée")
            return
        
        # ✅ CORRECTION: Nettoyer l'URL du repository si elle provient de Monday.com
        if isinstance(repo_url, str):
            import re
            # Format Monday.com: "GitHub - user/repo - https://github.com/user/repo"
            https_match = re.search(r'(https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?)', repo_url)
            if https_match:
                cleaned_url = https_match.group(1)
                if cleaned_url.endswith('.git'):
                    cleaned_url = cleaned_url[:-4]
                if cleaned_url != repo_url:
                    logger.info(f"🧹 URL repository nettoyée pour update: '{repo_url[:50]}...' → '{cleaned_url}'")
                    repo_url = cleaned_url

        logger.info(f"🔄 Mise à jour de la colonne Repository URL pour {repo_url}")

        # Récupérer la dernière PR fusionnée
        last_pr_result = await github_pr_service.get_last_merged_pr(repo_url)

        if last_pr_result and last_pr_result.get("success"):
            # Construire l'URL à mettre à jour (URL de la dernière PR fusionnée)
            pr_url = last_pr_result.get("pr_url")
            pr_number = last_pr_result.get("pr_number")
            pr_title = last_pr_result.get("pr_title", "")
            merged_at = last_pr_result.get("merged_at", "")

            # ✅ SIMPLIFICATION: Le champ "text" est optionnel
            # Monday.com affichera automatiquement l'URL si "text" n'est pas fourni
            # On envoie simplement l'URL, monday_tool.py se chargera du formatage
            repository_url_value = pr_url  # Sera formaté en {"url": "..."} par monday_tool

            logger.info(f"📌 Dernière PR fusionnée: #{pr_number} - {pr_title}")
            logger.info(f"🔗 URL à mettre à jour: {pr_url}")

            # Mettre à jour la colonne Repository URL
            update_result = await monday_tool._arun(
                action="update_column_value",
                item_id=monday_item_id,
                column_id=settings.monday_repository_url_column_id,
                value=repository_url_value
            )

            # ✅ VALIDATION ROBUSTE: Vérifier le résultat de mise à jour Monday.com
            if update_result and update_result.get("success"):
                logger.info("✅ Colonne Repository URL mise à jour avec succès")

                # ✅ NOUVEAU: Sauvegarder l'URL en base de données
                save_success = await _save_last_merged_pr_to_database(state, pr_url)
                if not save_success:
                    logger.warning("⚠️ Échec sauvegarde last_merged_pr_url en base (non-bloquant)")

                # Ajouter un message dans les résultats
                if "ai_messages" in state["results"]:
                    state["results"]["ai_messages"].append(
                        f"✅ Repository URL mis à jour: PR #{pr_number} fusionnée"
                    )

                # Stocker l'info dans les résultats
                state["results"]["repository_url_updated"] = {
                    "success": True,
                    "pr_url": pr_url,
                    "pr_number": pr_number,
                    "merged_at": merged_at
                }
            else:
                # ✅ AMÉLIORATION: Gestion d'erreur plus robuste avec détails
                error_details = {}
                if update_result:
                    error_details = {
                        "error": update_result.get("error", "Erreur inconnue"),
                        "column_id": settings.monday_repository_url_column_id,
                        "item_id": monday_item_id,
                        "attempted_value": pr_url
                    }
                    error_msg = update_result.get("error", "Erreur inconnue")
                else:
                    error_msg = "Résultat vide de l'API Monday.com"
                    error_details = {"error": "API returned None result"}

                logger.warning(f"⚠️ Échec mise à jour Repository URL: {error_msg}")
                logger.debug(f"🔍 Détails erreur Repository URL: {error_details}")

                if "ai_messages" in state["results"]:
                    state["results"]["ai_messages"].append(
                        f"⚠️ Échec mise à jour Repository URL: {error_msg}"
                    )

                # ✅ NOUVEAU: Stocker les erreurs pour debug
                state["results"]["repository_url_error"] = {
                    "success": False,
                    "error": error_msg,
                    "details": error_details,
                    "attempted_url": pr_url
                }
        else:
            # Aucune PR fusionnée trouvée, mettre à jour avec l'URL du repo de base
            logger.info(f"📝 Aucune PR fusionnée trouvée, mise à jour avec l'URL du repository: {repo_url}")

            # ✅ SIMPLIFICATION: Envoyer directement l'URL
            # monday_tool.py se chargera de formater en {"url": "..."}
            update_result = await monday_tool._arun(
                action="update_column_value",
                item_id=monday_item_id,
                column_id=settings.monday_repository_url_column_id,
                value=repo_url  # Sera formaté automatiquement
            )

            if update_result and update_result.get("success"):
                logger.info("✅ Colonne Repository URL mise à jour avec l'URL du repository")

                if "ai_messages" in state["results"]:
                    state["results"]["ai_messages"].append(
                        f"📝 Repository URL mis à jour: {repo_url}"
                    )

                state["results"]["repository_url_updated"] = {
                    "success": True,
                    "url": repo_url,
                    "type": "repository_base_url"
                }
            else:
                error_msg = update_result.get("error", "Erreur inconnue") if update_result else "Résultat vide"
                logger.warning(f"⚠️ Échec mise à jour Repository URL: {error_msg}")

    except Exception as e:
        logger.warning(f"⚠️ Erreur lors de la mise à jour de Repository URL: {e}")
        # Ne pas bloquer le workflow en cas d'erreur
        if "ai_messages" in state.get("results", {}):
            state["results"]["ai_messages"].append(
                f"⚠️ Erreur mise à jour Repository URL: {str(e)}"
            )


async def _save_last_merged_pr_to_database(state: GraphState, last_merged_pr_url: str) -> bool:
    """
    Sauvegarde l'URL de la dernière PR fusionnée en base de données.

    Args:
        state: État du workflow contenant le db_run_id
        last_merged_pr_url: URL de la dernière PR fusionnée

    Returns:
        True si sauvegarde réussie, False sinon
    """
    try:
        # Récupérer le db_run_id depuis l'état
        db_run_id = state.get("db_run_id") or state.get("run_id")

        if not db_run_id:
            logger.warning("⚠️ Aucun db_run_id trouvé - impossible de sauvegarder last_merged_pr_url en base")
            return False

        # Utiliser le service de persistence
        from services.database_persistence_service import db_persistence

        if not db_persistence.pool:
            logger.warning("⚠️ Pool de connexion non initialisé - impossible de sauvegarder last_merged_pr_url")
            return False

        # Sauvegarder l'URL en base
        success = await db_persistence.update_last_merged_pr_url(db_run_id, last_merged_pr_url)

        if success:
            logger.info(f"💾 URL dernière PR fusionnée sauvegardée en base: {last_merged_pr_url}")

            # Ajouter un message dans les résultats
            if "ai_messages" in state.get("results", {}):
                state["results"]["ai_messages"].append(
                    "💾 Dernière PR fusionnée sauvegardée en base de données"
                )

            return True
        else:
            logger.warning("⚠️ Échec de la sauvegarde de last_merged_pr_url en base")
            return False

    except Exception as e:
        logger.error(f"❌ Erreur lors de la sauvegarde de last_merged_pr_url: {e}")
        return False
