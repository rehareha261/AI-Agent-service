"""
Nœud de préparation de l'environnement.

Ce module prépare l'environnement de travail pour les tâches :
- Clone du repository Git
- Création et checkout de la branche
- Installation des dépendances
- Configuration de l'espace de travail
"""

import re
from typing import Optional, Any
from models.state import GraphState
from models.schemas import GitOperationResult
from tools.claude_code_tool import ClaudeCodeTool
from tools.monday_tool import MondayTool
from utils.logger import get_logger
from utils.persistence_decorator import with_persistence
from utils.github_parser import extract_github_url_from_description

logger = get_logger(__name__)


async def _extract_repository_url_from_monday_updates(task_id: str) -> str:
    """
    Extrait l'URL du repository GitHub depuis les updates Monday.com.

    Args:
        task_id: ID de la tâche Monday.com

    Returns:
        URL du repository ou chaîne vide si non trouvée
    """
    try:
        # Initialiser l'outil Monday
        monday_tool = MondayTool()

        # ✅ CORRECTION: Vérifier la configuration Monday.com avant l'appel
        if not hasattr(monday_tool, 'api_token') or not monday_tool.api_token:
            logger.info("💡 Monday.com non configuré - extraction URL GitHub ignorée")
            return ""

        logger.info(f"🔍 Recherche URL GitHub dans les updates Monday.com pour task {task_id}")

        # Récupérer les updates
        try:
            result = await monday_tool._get_item_updates(task_id)
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de la récupération des updates Monday.com: {e}")
            return ""

        # ✅ AMÉLIORATION: Gestion robuste de tous les cas de réponse
        if not isinstance(result, dict):
            logger.error(f"❌ Résultat _get_item_updates invalide (type {type(result)}): {result}")
            return ""

        if not result.get("success", False):
            error_msg = result.get("error", "Erreur inconnue")
            logger.warning(f"⚠️ Impossible de récupérer les updates pour l'item {task_id}: {error_msg}")
            return ""

        updates = result.get("updates", [])
        if not isinstance(updates, list):
            logger.warning(f"⚠️ Updates invalides pour l'item {task_id} (type {type(updates)})")
            return ""

        if len(updates) == 0:
            logger.warning(f"⚠️ Aucun update trouvé pour l'item {task_id}")
            return ""

        logger.info(f"📋 {len(updates)} updates trouvées pour item {task_id}, recherche d'URLs GitHub...")

        # ✅ AMÉLIORATION: Patterns de détection plus robustes
        github_patterns = [
            # URLs complètes HTTPS (plus strict)
            r'https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?(?:/[^\s]*)?',

            # URLs avec contexte descriptif
            r'(?:repository|repo|projet|github|code|source)[\s:=]*https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?',

            # URLs SSH
            r'git@github\.com:([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?',

            # URLs courtes  -- Éviter les faux positifs
            r'github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?(?!/[\w-]+(?:\.[\w-]+)*$)',

            # Liens Markdown
            r'\[.*?\]\(https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?\)',

            # Patterns avec mots-clés français/anglais
            r'(?:pour|for|from|de|du|vers|to)[\s:]*https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?'
        ]

        # Rechercher dans toutes les updates (du plus récent au plus ancien)
        for i, update in enumerate(updates):
            if not isinstance(update, dict):
                continue

            body = update.get("body", "")
            update_type = update.get("type", "unknown")
            update_id = update.get("id", f"update_{i}")

            if not body or not isinstance(body, str):
                continue

            logger.debug(f"🔍 Analyse {update_type} {update_id}: {body[:100]}...")

            # Tester chaque pattern
            for pattern_idx, pattern in enumerate(github_patterns):
                matches = re.findall(pattern, body, re.IGNORECASE)
                if matches:
                    # Prendre le premier match valide
                    match = matches[0]

                    # Construire l'URL selon le type de match
                    if isinstance(match, tuple) and len(match) >= 2:
                        # Match avec groupes (owner, repo)
                        owner, repo = match[0], match[1]
                        url = f"https://github.com/{owner}/{repo}"
                    elif isinstance(match, str):
                        # Match simple - peut être une URL complète
                        url = match
                    else:
                        continue

                    # Normaliser l'URL
                    if not url.startswith('http'):
                        url = f"https://{url}"
                    if url.endswith('.git'):
                        url = url[:-4]

                    # Validation basique de l'URL
                    if re.match(r'https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$', url):
                        logger.info(f"✅ URL repository trouvée avec pattern {pattern_idx + 1} dans {update_type} {update_id}: {url}")
                        logger.debug(f"   Texte source: {body[:200]}...")
                        return url
                    else:
                        logger.debug(f"⚠️ URL GitHub invalide trouvée: {url}")

        logger.warning("⚠️ Aucune URL GitHub trouvée dans les updates Monday.com")
        return ""

    except Exception as e:
        logger.error(f"❌ Erreur lors de l'extraction depuis les updates Monday.com: {e}")
        return ""


@with_persistence("prepare_environment")
async def prepare_environment(state: GraphState) -> GraphState:
    """
    Nœud de préparation de l'environnement.
    
    Ce nœud :
    1. Clone le repository GitHub
    2. Crée et checkout une nouvelle branche
    3. Installe les dépendances si nécessaire
    4. Configure l'espace de travail
    
    Args:
        state: État actuel du graphe
        
    Returns:
        État mis à jour avec l'environnement préparé
    """
    logger.info(f"🚀 Préparation de l'environnement pour: {state['task'].title}")
    
    # ✅ CORRECTION CRITIQUE: Assurer l'intégrité de l'état dès le début
    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)

    # Marquer le nœud comme en cours
    state["current_node"] = "prepare_environment"
    
    # Initialiser ai_messages si nécessaire
    if "ai_messages" not in state["results"]:
        state["results"]["ai_messages"] = []

    # Mettre à jour le statut
    state["results"]["current_status"] = "preparing".lower()
    state["results"]["ai_messages"].append("Début de la préparation de l'environnement...")

    try:
        # Initialiser l'outil Claude Code
        claude_tool = ClaudeCodeTool()

        # Déterminer l'URL du repository
        repo_url = None
        
        # 1. Vérifier la colonne repository_url de Monday.com (priorité haute)
        if hasattr(state["task"], 'repository_url') and state["task"].repository_url:
            repo_url = state["task"].repository_url.strip()
            logger.info(f"✅ URL repository depuis Monday.com: {repo_url}")
        
        # 2. Fallback: Rechercher dans la description de la tâche
        if not repo_url and hasattr(state["task"], 'description') and state["task"].description:
            repo_url = extract_github_url_from_description(state["task"].description)
            if repo_url:
                logger.info(f"✅ URL repository depuis description: {repo_url}")
        
        # 3. Fallback: Rechercher dans les updates Monday.com
        if not repo_url:
            logger.info(f"🔍 Tentative d'extraction URL GitHub depuis les updates Monday.com...")
            try:
                repo_url = await _extract_repository_url_from_monday_updates(str(state["task"].task_id))
            except Exception as e:
                logger.warning(f"⚠️ Erreur lors de l'extraction URL repository depuis Monday.com: {e}")
                repo_url = ""
            
            if repo_url:
                logger.info(f"✅ URL GitHub extraite des updates Monday.com: {repo_url}")
            else:
                logger.warning(f"⚠️ Aucune URL GitHub trouvée dans la description: {state['task'].description[:100]}...")

        # ✅ VALIDATION FINALE: Vérifier qu'on a bien une URL
        if not repo_url or not repo_url.strip():
            error_msg = (
                "❌ URL du repository non trouvée dans la tâche Monday.com.\n\n"
                "💡 SOLUTION: Ajoutez l'URL GitHub de l'une des façons suivantes:\n\n"
                "   1️⃣ Dans la colonne 'repository_url' de Monday.com\n"
                "   2️⃣ Dans la description de la tâche, par exemple:\n"
                "      • 'Implémenter pour: https://github.com/user/repo'\n"
                "      • 'Repository: https://github.com/user/repo'\n"
                "      • 'Code source: https://github.com/user/repo'\n\n"
                "   3️⃣ Dans un commentaire/update sur la tâche Monday.com:\n"
                "      • 'URL: https://github.com/user/repo'\n"
                "      • 'Repo: https://github.com/user/repo'\n\n"
                "🔗 L'URL sera automatiquement détectée et utilisée par le système."
            )
            logger.error(error_msg)

            # ✅ DEBUG: Afficher les informations disponibles
            task_info = {
                "title": getattr(state["task"], 'title', 'N/A'),
                "repository_url": getattr(state["task"], 'repository_url', 'N/A'),
                "description": getattr(state["task"], 'description', 'N/A')[:200] + "..." if getattr(state["task"], 'description', '') else 'N/A'
            }
            logger.error(f"📋 Informations tâche disponibles: {task_info}")

            state["error"] = error_msg
            state["results"]["current_status"] = "failed".lower()
            return state

        # ✅ ROBUSTESSE: Gestion intelligente et validée des noms de branche
        branch_name = _resolve_branch_name(state["task"], state.get("workflow_id"))
        
        logger.info(f"Configuration de l'environnement - Repo: {repo_url}, Branche: {branch_name}")

        # Configurer l'environnement avec Claude Tool
        setup_result = await claude_tool._arun(
            action="setup_environment",
            repo_url=repo_url,
            branch=branch_name
        )

        if setup_result["success"]:
            # Créer un résultat Git structuré
            git_result = GitOperationResult(
                success=True,
                operation="setup_environment",
                message="Environnement configuré avec succès",
                branch_name=branch_name
            )

            # ✅ CORRECTION CRITIQUE: S'assurer que le working_directory persiste
            working_dir = setup_result["working_directory"]
            
            # ✅ AMÉLIORATION: Validation robuste du working_directory
            import os
            if not working_dir:
                logger.error(f"❌ Working directory non défini dans setup_result")
                state["error"] = f"Working directory non défini dans le résultat du setup"
                state["results"]["current_status"] = "failed".lower()
                return state
            
            # Convertir en string si nécessaire et nettoyer le chemin
            working_dir = os.path.abspath(str(working_dir))
            
            if not os.path.exists(working_dir):
                logger.error(f"❌ Working directory inexistant après setup: {working_dir}")
                state["error"] = f"Working directory créé mais introuvable: {working_dir}"
                state["results"]["current_status"] = "failed".lower()
                return state
            
            # Stocker dans plusieurs endroits pour assurer la propagation
            state["results"]["git_result"] = git_result
            state["results"]["working_directory"] = working_dir
            state["working_directory"] = working_dir  # Au niveau racine pour propagation
            state["results"]["prepare_result"] = setup_result
            
            # ✅ CORRECTION CRITIQUE: Sauvegarder les informations Git dans l'état
            state["results"]["repository_url"] = repo_url
            state["results"]["git_branch"] = branch_name
            
            # ✅ CORRECTION CRITIQUE: Mettre à jour la tâche elle-même
            if hasattr(state["task"], '__dict__'):
                state["task"].git_branch = branch_name
                state["task"].repository_url = repo_url
            
            # ✅ NOUVELLE PROTECTION: Marquer le répertoire comme persistant
            state["results"]["working_directory_persistent"] = True
            state["results"]["environment_ready"] = True

            logger.info(f"✅ Environnement préparé avec succès: {working_dir}")
            state["results"]["ai_messages"].append(f"✅ Environnement configuré: {working_dir}")
            state["results"]["current_status"] = "environment_ready".lower()
            
        else:
            error_msg = f"Échec préparation: {setup_result.get('error', 'Erreur inconnue')}"
            logger.error(f"❌ {error_msg}")
            state["error"] = error_msg
            state["results"]["current_status"] = "failed".lower()
            state["results"]["ai_messages"].append(f"❌ {error_msg}")

        logger.info("🏁 Préparation terminée - Statut: ✅")
        return state

    except Exception as e:
        error_msg = f"Exception lors de la préparation: {str(e)}"
        logger.error(f"❌ {error_msg}")
        state["error"] = error_msg
        state["results"]["current_status"] = "failed".lower()
        state["results"]["ai_messages"].append(f"❌ {error_msg}")
        return state


def _is_test_task(task_id: str) -> bool:
    """Vérifie si la tâche est une tâche de test."""
    if not task_id:
        return False
    
    test_patterns = [
        "test_connection",
        "test_",
        "sandbox",
        "demo",
        "_test"
    ]
    
    task_id_lower = task_id.lower()
    return any(pattern in task_id_lower for pattern in test_patterns)


def _handle_test_task(state: GraphState) -> GraphState:
    """Gère les tâches de test avec un environnement simulé."""
    
    logger.info("🧪 Gestion d'une tâche de test avec environnement simulé")
    
    # Initialiser les résultats de base
    state["results"]["current_status"] = "IN_PROGRESS".lower()
    state["results"]["ai_messages"].append("🧪 Tâche de test - Environnement simulé")
    
    # Créer un résultat simulé
    import tempfile
    test_workspace = tempfile.mkdtemp(prefix="test_workspace_")
    
    git_result = GitOperationResult(
        success=True,
        operation="test_environment_setup",
        message="Environnement de test simulé créé avec succès",
        branch_name=state["task"].git_branch or state["task"].branch_name
    )
    
    # Mettre à jour l'état avec les informations simulées
    state["results"]["git_result"] = git_result
    state["results"]["working_directory"] = test_workspace
    state["working_directory"] = test_workspace
    state["results"]["last_operation_result"] = "Test environment created"
    state["results"]["should_continue"] = True
    
    # Simuler un repository URL de test
    if not state["task"].repository_url:
        state["task"].repository_url = "https://github.com/test/test-repo"
    
    logger.info(f"✅ Environnement de test créé: {test_workspace}")
    logger.info("🧪 Préparation de tâche de test terminée")
    
    return state


def _resolve_branch_name(task: Any, workflow_id: Optional[str] = None) -> str:
    """
    Résout le nom de branche avec génération intelligente et validation complète.
    
    Cette fonction garantit la génération de noms de branche valides selon les conventions Git,
    avec gestion des collisions et préservation de l'unicité.
    
    Args:
        task: Objet tâche contenant les informations de base
        workflow_id: ID du workflow pour l'unicité
        
    Returns:
        Nom de branche valide et unique
    """
    import re
    import hashlib
    from datetime import datetime
    from typing import Optional
    
    # Si une branche est déjà définie, la valider et la retourner
    existing_branch = getattr(task, 'git_branch', None) or getattr(task, 'branch_name', None)
    if existing_branch:
        validated_branch = _validate_and_sanitize_branch_name(existing_branch)
        if validated_branch:
            logger.info(f"🌿 Branche existante validée: {validated_branch}")
            return validated_branch
        else:
            logger.warning(f"⚠️ Branche invalide '{existing_branch}', génération automatique...")
    
    # Génération automatique intelligente
    logger.info("🌿 Génération automatique du nom de branche...")
    
    try:
        # ✅ ÉTAPE 1: Analyser le titre pour détecter le type de tâche
        task_title = getattr(task, 'title', '') or 'task'
        task_type = _detect_task_type(task_title)
        
        # ✅ ÉTAPE 2: Nettoyer et structurer le titre
        clean_title = _clean_title_for_branch(task_title)
        
        # ✅ ÉTAPE 3: Créer un identifiant unique
        unique_suffix = _generate_unique_suffix(task, workflow_id)
        
        # ✅ ÉTAPE 4: Assembler selon les conventions
        if len(clean_title) > 40:  # Titre très long
            # Utiliser un hash pour éviter les noms trop longs
            title_hash = hashlib.md5(clean_title.encode()).hexdigest()[:8]
            branch_name = f"{task_type}/{title_hash}-{unique_suffix}"
        else:
            branch_name = f"{task_type}/{clean_title}-{unique_suffix}"
        
        # ✅ ÉTAPE 5: Validation finale
        final_branch = _validate_and_sanitize_branch_name(branch_name)
        
        if not final_branch:
            # Fallback ultime
            fallback_branch = f"feature/auto-{unique_suffix}"
            logger.warning(f"⚠️ Utilisation du nom de branche de fallback: {fallback_branch}")
            return fallback_branch
        
        logger.info(f"🌿 Branche générée avec succès: {final_branch}")
        return final_branch
        
    except Exception as e:
        logger.error(f"❌ Erreur génération nom de branche: {e}")
        # Fallback d'urgence
        emergency_branch = f"feature/emergency-{datetime.now().strftime('%m%d%H%M')}"
        logger.warning(f"🆘 Nom de branche d'urgence: {emergency_branch}")
        return emergency_branch


def _detect_task_type(title: str) -> str:
    """
    Détecte le type de tâche à partir du titre pour choisir le préfixe approprié.
    
    Returns:
        Préfixe de branche (feature, bugfix, hotfix, etc.)
    """
    # ✅ ROBUSTESSE: Gérer les cas de titre None ou vide
    if not title or not isinstance(title, str):
        return 'feature'
    
    title_lower = title.lower()
    
    # ✅ AMÉLIORATION: Prioriser "urgent" et "critique" pour hotfix avant bugfix
    if any(keyword in title_lower for keyword in ['urgent', 'critique', 'hotfix', 'critical']):
        return 'hotfix'
    elif any(keyword in title_lower for keyword in ['bug', 'fix', 'erreur', 'correct', 'réparer']):
        return 'bugfix'
    elif any(keyword in title_lower for keyword in ['test', 'testing', 'spec']):
        return 'test'
    elif any(keyword in title_lower for keyword in ['doc', 'documentation', 'readme']):
        return 'docs'
    elif any(keyword in title_lower for keyword in ['refactor', 'restructur', 'clean']):
        return 'refactor'
    else:
        return 'feature'  # Par défaut


def _clean_title_for_branch(title: str) -> str:
    """
    Nettoie le titre pour créer un nom de branche Git valide.
    
    Returns:
        Titre nettoyé et validé
    """
    import re
    
    # Supprimer les caractères spéciaux et accents
    title = re.sub(r'[àáâãäå]', 'a', title)
    title = re.sub(r'[èéêë]', 'e', title)
    title = re.sub(r'[ìíîï]', 'i', title)
    title = re.sub(r'[òóôõö]', 'o', title)
    title = re.sub(r'[ùúûü]', 'u', title)
    title = re.sub(r'[ç]', 'c', title)
    title = re.sub(r'[ñ]', 'n', title)
    
    # Garder seulement les caractères alphanumériques, espaces et tirets
    title = re.sub(r'[^a-zA-Z0-9\s\-_]', '', title)
    
    # Remplacer les espaces multiples par des tirets
    title = re.sub(r'\s+', '-', title.strip())
    
    # Supprimer les tirets multiples
    title = re.sub(r'-+', '-', title)
    
    # Supprimer les tirets en début/fin
    title = title.strip('-_')
    
    # Convertir en minuscules
    title = title.lower()
    
    # Limiter la longueur
    if len(title) > 50:
        title = title[:47] + '...'
    
    return title if title else 'unnamed-task'


def _generate_unique_suffix(task: Any, workflow_id: Optional[str] = None) -> str:
    """
    Génère un suffixe unique pour éviter les collisions de noms de branche.
    
    Returns:
        Suffixe unique basé sur l'ID de tâche, workflow et timestamp
    """
    from datetime import datetime
    import hashlib
    
    # Collecter les identifiants disponibles
    identifiers = []
    
    if hasattr(task, 'task_id') and task.task_id:
        identifiers.append(str(task.task_id))
    
    if workflow_id:
        identifiers.append(str(workflow_id))
    
    # Timestamp pour l'unicité temporelle
    timestamp = datetime.now().strftime('%m%d-%H%M')
    identifiers.append(timestamp)
    
    # Si nous avons des IDs spécifiques, les utiliser
    if len(identifiers) > 1:  # Plus que juste le timestamp
        # Créer un hash court des IDs
        combined_ids = '-'.join(identifiers[:-1])  # Sans le timestamp
        id_hash = hashlib.md5(combined_ids.encode()).hexdigest()[:6]
        return f"{id_hash}-{timestamp[-4:]}"  # 6 chars hash + 4 chars time
    else:
        # Fallback sur timestamp étendu
        return datetime.now().strftime('%m%d-%H%M%S')


def _validate_and_sanitize_branch_name(branch_name: str) -> Optional[str]:
    """
    Valide et nettoie un nom de branche selon les règles Git.
    
    Règles Git pour les noms de branche:
    - Pas de caractères spéciaux (sauf - et _)
    - Pas de .. ou @
    - Pas de / au début ou à la fin
    - Longueur raisonnable
    
    Returns:
        Nom de branche valide ou None si impossible à corriger
    """
    import re
    from typing import Optional
    
    if not branch_name or not isinstance(branch_name, str):
        return None
    
    # Supprimer les espaces en début/fin
    branch_name = branch_name.strip()
    
    # Vérifier la longueur maximum
    if len(branch_name) > 250:  # Limite Git
        return None
    
    # Interdire certains patterns dangereux
    if '..' in branch_name or '@' in branch_name:
        return None
    
    # Nettoyer les caractères invalides
    branch_name = re.sub(r'[^a-zA-Z0-9\-_/]', '-', branch_name)
    
    # Nettoyer les tirets multiples
    branch_name = re.sub(r'-+', '-', branch_name)
    
    # Supprimer les / en début/fin
    branch_name = branch_name.strip('/')
    
    # Vérifier qu'il reste quelque chose de valide
    if not branch_name or branch_name in ['.', '..']:
        return None
    
    # Vérifier le format final
    if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-_/]*[a-zA-Z0-9]$', branch_name):
        return branch_name
    elif len(branch_name) == 1 and re.match(r'^[a-zA-Z0-9]$', branch_name):
        return branch_name
    else:
        return None
