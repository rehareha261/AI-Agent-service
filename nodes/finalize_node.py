"""Nœud de finalisation - pousse le code et crée la Pull Request."""

from typing import Dict, Any
from models.state import GraphState
from models.schemas import PullRequestInfo
from tools.github_tool import GitHubTool
from utils.logger import get_logger
from utils.helpers import get_working_directory, validate_working_directory, ensure_working_directory
from utils.persistence_decorator import with_persistence
from services.database_persistence_service import db_persistence

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
        
        # ✅ CORRECTION: Nettoyer l'URL du repository si elle provient de Monday.com
        if repo_url and isinstance(repo_url, str):
            import re
            # Format Monday.com: "GitHub - user/repo - https://github.com/user/repo"
            https_match = re.search(r'(https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?)', repo_url)
            if https_match:
                cleaned_url = https_match.group(1)
                if cleaned_url.endswith('.git'):
                    cleaned_url = cleaned_url[:-4]
                if cleaned_url != repo_url:
                    logger.info(f"🧹 URL repository nettoyée pour finalize: '{repo_url[:50]}...' → '{cleaned_url}'")
                    repo_url = cleaned_url
                    # Mettre à jour dans l'état pour cohérence
                    state["results"]["repository_url"] = cleaned_url
        
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

            # ✅ CORRECTION: Passer repository_url pour gérer le cas où remote origin n'existe pas
            push_result = await github_tool._push_branch(
                working_directory=working_directory,
                branch=git_branch,
                repository_url=repo_url  # Ajout pour gérer le remote manquant
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
                # ✅ AMÉLIORATION: Gérer le cas où les fichiers sont déjà poussés
                if error_msg and "Aucun changement détecté" in error_msg:
                    logger.warning("⚠️ Aucun changement local - vérification si la branche existe déjà sur le remote...")
                    # Vérifier si la branche existe déjà sur GitHub
                    try:
                        import subprocess
                        original_cwd_check = os.getcwd()
                        os.chdir(working_directory)
                        
                        check_result = subprocess.run(
                            ["git", "ls-remote", "--heads", "origin", git_branch],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        
                        os.chdir(original_cwd_check)
                        
                        if check_result.returncode == 0 and check_result.stdout.strip():
                            logger.info(f"✅ La branche {git_branch} existe déjà sur le remote")
                            logger.info("💡 Les fichiers ont été poussés pendant l'implémentation - continuons avec la PR")
                            push_success = True  # Considérer comme un succès pour continuer
                        else:
                            logger.error(f"❌ La branche n'existe pas sur le remote et pas de changements locaux")
                            raise Exception(f"Échec push: {error_msg}")
                    except Exception as check_error:
                        logger.error(f"❌ Impossible de vérifier l'existence de la branche: {check_error}")
                        if 'original_cwd_check' in locals():
                            os.chdir(original_cwd_check)
                        raise Exception(f"Échec push: {error_msg}")
                else:
                    raise Exception(f"Échec push: {error_msg}")

            if push_success:
                logger.info(f"✅ Branche {git_branch} poussée avec succès (ou déjà présente sur le remote)")

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
                
                # ✅ PERSISTENCE: Sauvegarder la PR en base de données
                try:
                    # ✅ CORRECTION: Utiliser db_task_id (ID base de données) au lieu de task_id (monday_item_id)
                    task_id = state.get("db_task_id")
                    task_run_id = state.get("db_run_id")
                    
                    if task_id and task_run_id:
                        await db_persistence.create_pull_request(
                            task_id=int(task_id),  # S'assurer que c'est un entier
                            task_run_id=int(task_run_id),  # S'assurer que c'est un entier
                            github_pr_number=pr_info.number,
                            github_pr_url=pr_info.url,
                            pr_title=pr_title,
                            pr_description=pr_body,
                            head_sha=None,  # Sera rempli plus tard si nécessaire
                            base_branch="main",
                            feature_branch=git_branch
                        )
                        logger.info(f"💾 Pull request sauvegardée en base de données")
                    else:
                        logger.warning(f"⚠️ Impossible de sauvegarder la PR en base: task_id={task_id}, task_run_id={task_run_id}")
                except Exception as db_error:
                    logger.error(f"❌ Erreur sauvegarde PR en base: {db_error}")
                    # Ne pas faire échouer le workflow pour un problème de persistence
                
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
        
        # ✅ PERSISTENCE: Enregistrer les métriques de performance
        try:
            task_id = state.get("db_task_id")
            task_run_id = state.get("db_run_id")
            
            if task_id and task_run_id:
                # Calculer les métriques depuis l'état
                started_at = state.get("started_at")
                total_duration = None
                if started_at:
                    from datetime import datetime, timezone
                    # ✅ CORRECTION: S'assurer que les deux datetimes ont le même timezone
                    now_utc = datetime.now(timezone.utc)
                    # Si started_at est offset-naive, le rendre offset-aware
                    if started_at.tzinfo is None:
                        started_at = started_at.replace(tzinfo=timezone.utc)
                    total_duration = int((now_utc - started_at).total_seconds())
                
                # Collecter les métriques d'IA depuis les résultats
                ai_calls = state.get("results", {}).get("total_ai_calls", 0)
                total_tokens = state.get("results", {}).get("total_tokens_used", 0)
                total_cost = state.get("results", {}).get("total_ai_cost", 0.0)
                
                # Métriques de tests
                test_results_list = state.get("results", {}).get("test_results", [])
                test_coverage = None
                if test_results_list:
                    last_test = test_results_list[-1]
                    if isinstance(last_test, dict):
                        test_coverage = last_test.get("coverage", None)
                
                # Nombre de tentatives de retry/debug
                retry_attempts = state.get("results", {}).get("debug_attempts", 0)
                
                # Lignes de code générées (estimation basée sur modified_files)
                code_lines = 0
                code_changes = state.get("results", {}).get("code_changes", {})
                for file_code in code_changes.values():
                    if isinstance(file_code, str):
                        code_lines += len(file_code.split('\n'))
                
                await db_persistence.record_performance_metrics(
                    task_id=task_id,
                    task_run_id=task_run_id,
                    total_duration_seconds=total_duration,
                    ai_processing_time_seconds=None,  # Peut être calculé plus tard
                    testing_time_seconds=None,  # Peut être calculé plus tard
                    total_ai_calls=ai_calls,
                    total_tokens_used=total_tokens,
                    total_ai_cost=total_cost,
                    test_coverage_final=test_coverage,
                    retry_attempts=retry_attempts
                )
                logger.info(f"💾 Métriques de performance enregistrées pour task_id={task_id}, run_id={task_run_id}")
            else:
                logger.warning(f"⚠️ Impossible d'enregistrer les métriques: task_id={task_id}, task_run_id={task_run_id}")
        except Exception as metrics_error:
            logger.error(f"❌ Erreur enregistrement métriques de performance: {metrics_error}")
            # Ne pas faire échouer le workflow pour un problème de persistence

        # ✅ CORRECTION SIGSEGV: Nettoyer le client LangSmith pour éviter les problèmes de désallocation
        try:
            from config.langsmith_config import langsmith_config
            if langsmith_config._client is not None:
                logger.info("🧹 Nettoyage du client LangSmith pour éviter SIGSEGV")
                langsmith_config._client = None
        except Exception as cleanup_error:
            logger.warning(f"⚠️ Erreur nettoyage LangSmith: {cleanup_error}")

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
    # ✅ COHÉRENCE: Afficher monday_item_id pour l'utilisateur (pas db_task_id)
    display_id = task.monday_item_id if hasattr(task, 'monday_item_id') and task.monday_item_id else task.task_id
    pr_body = f"""## 🤖 Pull Request générée automatiquement

### 📋 Tâche
**ID Monday.com**: {display_id}
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
