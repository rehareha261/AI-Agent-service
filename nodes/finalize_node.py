"""Nœud de finalisation - pousse le code et crée la Pull Request."""

from typing import Dict, Any
from models.state import GraphState
from models.schemas import PullRequestInfo
from tools.github_tool import GitHubTool
from utils.logger import get_logger
from utils.helpers import get_working_directory, validate_working_directory, ensure_working_directory
from utils.persistence_decorator import with_persistence

logger = get_logger(__name__)


@with_persistence("finalize_pr")
async def finalize_pr(state: GraphState) -> GraphState:
    """
    Nœud de finalisation : pousse le code et crée la Pull Request.

    Ce nœud :
    1. Pousse les changements vers GitHub
    2. Crée une Pull Request
    3. Ajoute des informations détaillées à la PR
    4. Prépare la mise à jour Monday

    Args:
        state: État actuel du graphe

    Returns:
        État mis à jour avec les informations de la PR
    """
    logger.info(f"🚀 Finalisation pour: {state['task'].title}")

    # ✅ CORRECTION CRITIQUE: Assurer l'intégrité de l'état dès le début
    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)

    # ✅ SÉCURITÉ: Initialiser les structures de données si nécessaire
    if "results" not in state or not isinstance(state["results"], dict):
        state["results"] = {}

    if "ai_messages" not in state["results"]:
        state["results"]["ai_messages"] = []

    if "error_logs" not in state["results"]:
        state["results"]["error_logs"] = []

    state["results"]["current_status"] = "FINALIZING".lower()
    state["results"]["ai_messages"].append("Début de la finalisation...")

    try:
        # ✅ CORRECTION ROBUSTE: Récupérer le répertoire de travail de manière sécurisée
        logger.info("🔍 Récupération du répertoire de travail...")
        working_directory = get_working_directory(state)
        logger.info(f"🔍 Répertoire de travail récupéré: {working_directory}")

        if not validate_working_directory(working_directory, "finalize_node"):
            logger.warning("⚠️ Répertoire de travail invalide, tentative de récupération...")
            try:
                working_directory = ensure_working_directory(state, "finalize_node_")
                logger.info(f"📁 Répertoire de travail de secours créé: {working_directory}")
            except Exception as e:
                error_msg = f"Impossible de créer un répertoire de travail pour la finalisation: {e}"
                logger.error(f"❌ {error_msg}")
                state["results"]["error_logs"].append(error_msg)
                state["results"]["ai_messages"].append(f"❌ {error_msg}")
                state["results"]["current_status"] = "failed"
                return state

        logger.info(f"🔍 Répertoire de travail validé: {working_directory}")
        task = state["task"]
        
        # ✅ CORRECTION: Rechercher les informations Git dans l'état puis dans la tâche
        repo_url = (
            state["results"].get("repository_url") or 
            getattr(task, 'repository_url', None) or 
            ""
        )
        git_branch = (
            state["results"].get("git_branch") or 
            getattr(task, 'git_branch', None) or 
            getattr(task, 'branch_name', None) or 
            ""
        )
        
        logger.info(f"🔍 Repository URL: {repo_url}")
        logger.info(f"🔍 Git branch: {git_branch}")

        # ✅ VALIDATION CRITIQUE: Vérifier les prérequis avant de continuer
        validation_errors = []
        
        if not repo_url or not repo_url.strip():
            validation_errors.append("URL du repository non définie")
        
        if not git_branch or not git_branch.strip():
            validation_errors.append("Branche Git non définie")
        
        if not working_directory:
            validation_errors.append("Répertoire de travail non défini")
            
        # Vérifier qu'il y a des fichiers modifiés
        modified_files = state["results"].get("modified_files", [])
        if not modified_files:
            logger.warning("⚠️ Aucun fichier modifié détecté dans results - tentative de détection avec Git...")
            
            # Tentative de détection avec Git comme fallback
            if working_directory:
                try:
                    import subprocess
                    import os
                    original_cwd = os.getcwd()
                    os.chdir(working_directory)
                    
                    # Détecter les fichiers modifiés avec git status
                    result = subprocess.run(
                        ["git", "status", "--porcelain"], 
                        capture_output=True, 
                        text=True, 
                        timeout=30
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        # Parser la sortie de git status
                        git_modified_files = []
                        for line in result.stdout.strip().split('\n'):
                            if line.strip():
                                # Format: "XY filename" où X et Y sont les statuts
                                status = line[:2]
                                filepath = line[3:]
                                git_modified_files.append(filepath)
                        
                        if git_modified_files:
                            logger.info(f"✅ {len(git_modified_files)} fichiers modifiés détectés avec Git: {git_modified_files[:3]}...")
                            state["results"]["modified_files"] = git_modified_files
                            modified_files = git_modified_files
                        else:
                            logger.warning("⚠️ Git status ne montre aucun fichier modifié")
                    else:
                        logger.warning("⚠️ Impossible d'exécuter git status")
                        
                    os.chdir(original_cwd)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Erreur lors de la détection Git: {e}")
                    if 'original_cwd' in locals():
                        os.chdir(original_cwd)
            
            if not modified_files:
                logger.warning("⚠️ Aucun fichier modifié détecté même avec Git - continuons quand même")
        
        if validation_errors:
            error_msg = f"Prérequis manquants pour la finalisation: {', '.join(validation_errors)}"
            logger.error(f"❌ {error_msg}")
            state["results"]["error_logs"].append(error_msg)
            state["results"]["ai_messages"].append(f"❌ {error_msg}")
            state["results"]["current_status"] = "failed_validation"
            
            # Continuer vers Monday pour signaler l'erreur mais ne pas essayer de créer la PR
            state["results"]["should_continue"] = True
            state["results"]["skip_github"] = True
            return state

        # ✅ CORRECTION: Créer la PR maintenant pour permettre la validation humaine
        state["results"]["ai_messages"].append("🚀 Création de la Pull Request...")

        # 1. Générer le contenu de la PR
        logger.info("🔍 Génération du contenu PR...")
        pr_title, pr_body = await _generate_pr_content(task, state)
        logger.info(f"🔍 PR title généré: {pr_title[:50]}...")

        # 2. Utiliser l'outil GitHub pour créer la PR
        logger.info("🔍 Initialisation GitHubTool...")
        github_tool = GitHubTool()

        # Pousser les changements et créer la PR
        try:
            # 1. Pousser la branche d'abord
            try:
                import subprocess
                import os
                original_cwd = os.getcwd()
                os.chdir(working_directory)
                
                # Vérifier la configuration Git
                config_result = subprocess.run(
                    ["git", "config", "--list"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if config_result.returncode == 0:
                    logger.info("✅ Configuration Git vérifiée")
                
                os.chdir(original_cwd)
            except Exception as e:
                logger.warning(f"⚠️ Impossible de vérifier la config Git: {e}")
                if 'original_cwd' in locals():
                    os.chdir(original_cwd)

            # Appel corrigé sans repo_url
            push_result = await github_tool._push_branch(
                working_directory=working_directory,
                branch=git_branch
            )
            logger.info(f"�� Résultat push reçu: {type(push_result)} - {push_result}")

            # GitOperationResult ou dictionnaire de fallback
            push_success = False
            if hasattr(push_result, 'success'):
                # C'est un objet GitOperationResult
                push_success = push_result.success
                error_msg = getattr(push_result, 'error', push_result.message) if not push_success else None
            elif isinstance(push_result, dict):
                # C'est un dictionnaire de fallback
                push_success = push_result.get("success", False)
                error_msg = push_result.get("error", "Erreur lors du push") if not push_success else None
            else:
                error_msg = "Résultat push invalide"

            if not push_success:
                raise Exception(f"Échec push: {error_msg}")

            logger.info(f"✅ Branche {git_branch} poussée avec succès")

            # 2. Ensuite créer la Pull Request
            pr_result = await github_tool._arun(
                action="create_pull_request",
                repo_url=repo_url,
                head_branch=git_branch,
                title=pr_title,
                body=pr_body
            )

            # ✅ VALIDATION RENFORCÉE: Vérification complète du résultat PR
            if pr_result and pr_result.get("success"):
                # Vérifier que les données de la PR sont présentes
                pr_info_dict = pr_result.get("pr_info")
                
                if not pr_info_dict:
                    raise ValueError("Données PR manquantes dans la réponse")
                
                # Validation des champs obligatoires
                required_fields = ["number", "url"]
                missing_fields = [field for field in required_fields if field not in pr_info_dict]
                
                if missing_fields:
                    raise ValueError(f"Champs PR manquants: {missing_fields}")
                
                # Validation des types et valeurs
                if not isinstance(pr_info_dict["number"], int) or pr_info_dict["number"] <= 0:
                    raise ValueError(f"Numéro PR invalide: {pr_info_dict['number']}")
                
                if not isinstance(pr_info_dict["url"], str) or not pr_info_dict["url"].startswith('http'):
                    raise ValueError(f"URL PR invalide: {pr_info_dict['url']}")

                # ✅ CRÉATION: Créer l'objet PullRequestInfo validé
                try:
                    pr_info = PullRequestInfo(**pr_info_dict)
                except Exception as schema_error:
                    raise ValueError(f"Erreur création objet PullRequestInfo: {schema_error}")

                state["results"]["pr_info"] = pr_info
                state["results"]["pr_url"] = pr_info.url
                state["results"]["pr_number"] = pr_info.number
                state["results"]["ai_messages"].append(f"✅ PR créée: #{pr_info.number} - {pr_info.url}")
                state["results"]["last_operation_result"] = f"PR créée: {pr_info.url}"

                logger.info(f"✅ PR créée avec succès - #{pr_info.number}: {pr_info.url}")
                
            elif pr_result and not pr_result.get("success"):
                # Erreur avec message spécifique
                error_msg = pr_result.get("error", "Erreur lors de la création de PR")
                raise Exception(f"GitHub API error: {error_msg}")
            else:
                # Pas de résultat du tout
                raise Exception("Aucune réponse de l'API GitHub pour la création de PR")

        except Exception as pr_error:
            error_msg = f"Exception lors de la création PR: {str(pr_error)}"
            state["results"]["error_logs"].append(error_msg)
            state["results"]["ai_messages"].append(f"❌ Exception PR: {error_msg}")
            logger.error(error_msg, exc_info=True)

        state["results"]["should_continue"] = True
        state["results"]["waiting_human_validation"] = True

        return state

    except Exception as e:
        error_msg = f"Exception lors de la finalisation: {str(e)}"
        logger.error(error_msg, exc_info=True)

        state["results"]["error_logs"].append(error_msg)
        state["results"]["ai_messages"].append(f"❌ Exception: {error_msg}")
        state["results"]["last_operation_result"] = error_msg
        state["results"]["should_continue"] = True  # Continuer vers Monday pour signaler l'erreur

    logger.info("🏁 Finalisation terminée")
    return state


async def _generate_pr_content(task, state: Dict[str, Any]) -> tuple[str, str]:
    """Génère le titre et la description de la Pull Request."""

    # Titre simple et descriptif
    pr_title = f"feat: {task.title}"

    # Corps de la PR
    pr_body = f"""## 🤖 Pull Request générée automatiquement

### 📋 Tâche
**ID**: {task.task_id}
**Titre**: {task.title}
**Priorité**: {task.priority}

### 📝 Description
{task.description}

### 🔧 Changements apportés
"""

    # Ajouter la liste des fichiers modifiés
    if state["results"].get("modified_files"):
        pr_body += "\n#### Fichiers modifiés:\n"
        for file_path in state["results"]["modified_files"]:
            pr_body += f"- `{file_path}`\n"

    # Ajouter les résultats des tests
    if state["results"].get("test_results"):
        latest_test = state["results"]["test_results"][-1]

        # Gérer à la fois les dictionnaires et les objets TestResult
        if hasattr(latest_test, 'success'):
            # C'est un objet TestResult
            test_success = latest_test.success
            test_command = getattr(latest_test, 'test_command', 'N/A')
        else:
            # C'est un dictionnaire
            test_success = latest_test.get("success", False)
            test_command = latest_test.get("command", "N/A")

        if test_success:
            pr_body += f"\n### ✅ Tests\n- ✅ Tests passés avec `{test_command}`\n"
        else:
            pr_body += f"\n### ⚠️ Tests\n- ⚠️ Derniers tests: `{test_command}` (voir logs)\n"

    # Ajouter les tentatives de debug si applicable
    if state["results"].get("debug_attempts", 0) > 0:
        pr_body += (f"\n### 🔧 Debug\n- 🔧 {state['results'].get('debug_attempts', 0)} "
                    f"tentative(s) de correction effectuée(s)\n")

    # Ajouter les logs d'erreurs importantes
    if state["results"].get("error_logs"):
        # Limiter aux 3 dernières erreurs pour ne pas surcharger
        recent_errors = state["results"]["error_logs"][-3:]
        pr_body += "\n### 📊 Informations de développement\n"
        pr_body += "<details><summary>Logs de développement (cliquer pour développer)</summary>\n\n"
        for error in recent_errors:
            pr_body += f"- {error}\n"
        pr_body += "\n</details>\n"

    # Footer
    pr_body += f"""
### 🎯 Prêt pour la revue
Cette Pull Request a été générée automatiquement par l'agent IA.
- ✅ Code implémenté selon les spécifications
- ✅ Tests validés
- ✅ Prêt pour la revue humaine

**Branche**: `{getattr(task, 'git_branch', 'N/A')}`
**Assigné**: {getattr(task, 'assignee', None) or 'Non assigné'}
"""

    return pr_title, pr_body


async def _generate_summary_comment(state: Dict[str, Any]) -> str:
    """Génère un commentaire de résumé pour la PR."""

    comment = "## 🤖 Résumé de l'implémentation automatique\n\n"

    # Statistiques
    comment += "### 📊 Statistiques\n"
    modified_files = len(state["results"].get("modified_files", []))
    test_results = state["results"].get("test_results", [])
    error_count = len(state["results"].get("error_logs", []))

    comment += f"- **Fichiers modifiés**: {modified_files}\n"
    comment += f"- **Tests exécutés**: {len(test_results)}\n"
    comment += f"- **Erreurs détectées**: {error_count}\n"

    return comment


def should_continue_to_update(state: Dict[str, Any]) -> bool:
    """Détermine si le workflow doit continuer vers la mise à jour Monday."""
    # Toujours continuer vers Monday pour mettre à jour le statut
    return True
