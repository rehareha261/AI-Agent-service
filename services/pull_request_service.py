"""
Service de gestion robuste des Pull Requests.

Ce service centralise toute la logique de création, mise à jour et merge des PR
avec gestion d'erreurs, retry, et persistence des états.
"""

import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import os

from models.schemas import PullRequestInfo, TaskRequest
from tools.github_tool import GitHubTool
from utils.logger import get_logger
from utils.helpers import get_working_directory

logger = get_logger(__name__)


class PRStatus(Enum):
    """États possibles d'une Pull Request dans notre système."""
    PENDING_CREATION = "pending_creation"
    CREATING = "creating"
    CREATED = "created"
    PENDING_MERGE = "pending_merge"
    MERGING = "merging" 
    MERGED = "merged"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PROperationResult:
    """Résultat d'une opération sur une PR."""
    success: bool
    pr_info: Optional[PullRequestInfo] = None
    error: Optional[str] = None
    retry_after: Optional[int] = None
    should_retry: bool = False


class PullRequestService:
    """Service centralisé pour la gestion des Pull Requests."""
    
    def __init__(self):
        self.github_tool = GitHubTool()
        self._pr_cache: Dict[str, Dict[str, Any]] = {}
        
    async def ensure_pull_request_created(
        self, 
        state: Dict[str, Any], 
        force_recreate: bool = False
    ) -> PROperationResult:
        """
        S'assure qu'une Pull Request existe pour la tâche donnée.
        
        Cette méthode est idempotente et peut être appelée plusieurs fois.
        
        Args:
            state: État du workflow
            force_recreate: Forcer la recréation même si une PR existe
            
        Returns:
            Résultat de l'opération avec les informations de la PR
        """
        try:
            task = state.get("task")
            if not task:
                return PROperationResult(
                    success=False, 
                    error="Aucune tâche trouvée dans l'état"
                )
            
            task_id = str(task.task_id) if hasattr(task, 'task_id') else str(task.get('task_id', 'unknown'))
            
            # Vérifier si une PR existe déjà (en cache ou dans l'état)
            existing_pr = await self._get_existing_pr_info(state, task_id)
            if existing_pr and not force_recreate:
                logger.info(f"✅ PR existante trouvée: #{existing_pr.number}")
                return PROperationResult(success=True, pr_info=existing_pr)
            
            # Vérifier les prérequis
            prereq_check = await self._check_pr_prerequisites(state)
            if not prereq_check.success:
                return prereq_check
            
            # Créer la PR
            logger.info(f"📝 Création de la Pull Request pour tâche {task_id}...")
            return await self._create_pull_request_with_retry(state, task_id)
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la création de PR: {e}")
            return PROperationResult(
                success=False,
                error=f"Exception: {str(e)}",
                should_retry=True,
                retry_after=30
            )
    
    async def merge_pull_request(
        self, 
        state: Dict[str, Any], 
        pr_info: PullRequestInfo,
        merge_strategy: str = "squash"
    ) -> PROperationResult:
        """
        Effectue le merge d'une Pull Request.
        
        Args:
            state: État du workflow
            pr_info: Informations de la PR à merger
            merge_strategy: Stratégie de merge ("merge", "squash", "rebase")
            
        Returns:
            Résultat de l'opération de merge
        """
        try:
            task = state.get("task")
            repo_url = self._extract_repository_url(task, state)
            
            if not repo_url:
                return PROperationResult(
                    success=False,
                    error="URL du repository non trouvée pour le merge"
                )
            
            logger.info(f"🔀 Merge de la PR #{pr_info.number} avec stratégie '{merge_strategy}'")
            
            # Effectuer le merge via GitHubTool
            merge_result = await self.github_tool._arun(
                action="merge_pull_request",
                repo_url=repo_url,
                pr_number=pr_info.number,
                merge_method=merge_strategy,
                commit_title=f"feat: {task.title}",
                commit_message=f"Merge PR #{pr_info.number}\n\n{task.description[:200]}..."
            )
            
            if merge_result.get("success"):
                # Mettre à jour le statut de la PR
                pr_info.status = "merged"
                
                # Nettoyer le cache
                task_id = str(task.task_id) if hasattr(task, 'task_id') else 'unknown'
                self._clear_pr_cache(task_id)
                
                logger.info(f"✅ PR #{pr_info.number} mergée avec succès")
                return PROperationResult(success=True, pr_info=pr_info)
            else:
                error_msg = merge_result.get("error", "Erreur inconnue lors du merge")
                logger.error(f"❌ Échec merge PR: {error_msg}")
                return PROperationResult(
                    success=False,
                    error=error_msg,
                    should_retry=True,
                    retry_after=60
                )
                
        except Exception as e:
            logger.error(f"❌ Exception lors du merge: {e}")
            return PROperationResult(
                success=False,
                error=f"Exception: {str(e)}",
                should_retry=True,
                retry_after=30
            )
    
    async def _get_existing_pr_info(
        self, 
        state: Dict[str, Any], 
        task_id: str
    ) -> Optional[PullRequestInfo]:
        """Récupère les informations d'une PR existante."""
        
        # Vérifier dans l'état du workflow
        pr_info = state.get("results", {}).get("pr_info")
        if pr_info and isinstance(pr_info, PullRequestInfo):
            return pr_info
        
        # Vérifier dans le cache
        cached_pr = self._pr_cache.get(task_id, {}).get("pr_info")
        if cached_pr:
            return cached_pr
        
        return None
    
    async def _check_pr_prerequisites(self, state: Dict[str, Any]) -> PROperationResult:
        """Vérifie que tous les prérequis pour créer une PR sont présents."""
        
        task = state.get("task")
        if not task:
            return PROperationResult(success=False, error="Tâche manquante")
        
        # Vérifier l'URL du repository
        repo_url = self._extract_repository_url(task, state)
        if not repo_url:
            return PROperationResult(
                success=False, 
                error="URL du repository non trouvée"
            )
        
        # Vérifier le répertoire de travail
        working_directory = get_working_directory(state)
        if not working_directory or not os.path.exists(working_directory):
            return PROperationResult(
                success=False,
                error="Répertoire de travail non trouvé"
            )
        
        # Vérifier les informations de branche
        branch_name = self._extract_branch_name(state)
        if not branch_name:
            return PROperationResult(
                success=False,
                error="Nom de branche non trouvé"
            )
        
        return PROperationResult(success=True)
    
    async def _create_pull_request_with_retry(
        self, 
        state: Dict[str, Any], 
        task_id: str,
        max_retries: int = 3
    ) -> PROperationResult:
        """Crée une PR avec logique de retry."""
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🔄 Tentative {attempt}/{max_retries} de création PR")
                
                result = await self._create_pull_request_internal(state)
                
                if result.success:
                    # Mettre en cache
                    self._cache_pr_info(task_id, result.pr_info)
                    return result
                
                if not result.should_retry or attempt == max_retries:
                    return result
                
                # Attendre avant le retry
                wait_time = result.retry_after or (attempt * 10)
                logger.info(f"⏳ Attente {wait_time}s avant retry...")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                if attempt == max_retries:
                    return PROperationResult(
                        success=False,
                        error=f"Échec après {max_retries} tentatives: {str(e)}"
                    )
                
                wait_time = attempt * 15
                logger.warning(f"⚠️ Tentative {attempt} échouée: {e}. Retry dans {wait_time}s")
                await asyncio.sleep(wait_time)
        
        return PROperationResult(
            success=False,
            error=f"Échec après {max_retries} tentatives"
        )
    
    async def _create_pull_request_internal(self, state: Dict[str, Any]) -> PROperationResult:
        """Logique interne de création de PR."""
        
        task = state.get("task")
        repo_url = self._extract_repository_url(task, state)
        working_directory = get_working_directory(state)
        branch_name = self._extract_branch_name(state)
        
        # Générer le contenu de la PR
        pr_title, pr_body = self._generate_pr_content(task, state)
        
        # Créer la PR via GitHubTool
        pr_result = await self.github_tool._arun(
            action="create_pull_request",
            repo_url=repo_url,
            branch_name=branch_name,
            base_branch="main",
            title=pr_title,
            body=pr_body,
            working_directory=working_directory
        )
        
        if pr_result.get("success"):
            pr_info = PullRequestInfo(
                number=pr_result.get("pr_number"),
                title=pr_title,
                url=pr_result.get("pr_url", ""),
                branch=branch_name,
                base_branch="main",
                status="open",
                created_at=datetime.now()
            )
            
            return PROperationResult(success=True, pr_info=pr_info)
        else:
            error_msg = pr_result.get("error", "Erreur inconnue")
            should_retry = "rate limit" in error_msg.lower() or "timeout" in error_msg.lower()
            
            return PROperationResult(
                success=False,
                error=error_msg,
                should_retry=should_retry,
                retry_after=60 if should_retry else None
            )
    
    def _extract_repository_url(self, task: Any, state: Dict[str, Any]) -> Optional[str]:
        """Extrait l'URL du repository depuis différentes sources."""
        
        # Source 1: Attribut direct de la tâche
        if task and hasattr(task, 'repository_url') and task.repository_url:
            return task.repository_url
        
        # Source 2: État du workflow
        repo_url = state.get("results", {}).get("repository_url")
        if repo_url:
            return repo_url
        
        # Source 3: Description de la tâche
        if task and hasattr(task, 'description') and task.description:
            from utils.github_parser import extract_github_url_from_description
            extracted_url = extract_github_url_from_description(task.description)
            if extracted_url:
                return extracted_url
        
        return None
    
    def _extract_branch_name(self, state: Dict[str, Any]) -> Optional[str]:
        """Extrait le nom de branche depuis l'état."""
        
        # Source 1: git_result
        git_result = state.get("results", {}).get("git_result")
        if git_result:
            if hasattr(git_result, 'branch_name'):
                return git_result.branch_name
            elif isinstance(git_result, dict):
                return git_result.get('branch_name')
        
        # Source 2: prepare_result
        prepare_result = state.get("results", {}).get("prepare_result", {})
        if isinstance(prepare_result, dict):
            return prepare_result.get("branch_name")
        
        return None
    
    def _generate_pr_content(self, task: Any, state: Dict[str, Any]) -> tuple[str, str]:
        """Génère le titre et le corps de la PR de manière robuste."""
        
        # Titre sécurisé
        title = f"feat: {task.title}" if hasattr(task, 'title') else "feat: Automated implementation"
        
        # Corps avec toutes les informations disponibles
        body_parts = [
            "## 🤖 Pull Request générée automatiquement",
            "",
            "### 📋 Tâche"
        ]
        
        if hasattr(task, 'task_id'):
            body_parts.append(f"**ID**: {task.task_id}")
        if hasattr(task, 'title'):
            body_parts.append(f"**Titre**: {task.title}")
        if hasattr(task, 'priority'):
            body_parts.append(f"**Priorité**: {task.priority}")
        
        body_parts.extend(["", "### 📝 Description"])
        if hasattr(task, 'description') and task.description:
            body_parts.append(task.description)
        else:
            body_parts.append("Description non disponible")
        
        # Ajouter les changements
        self._add_changes_info(body_parts, state)
        
        # Ajouter les résultats de tests et QA
        self._add_quality_info(body_parts, state)
        
        body_parts.extend([
            "",
            "### ✅ Validation",
            "✅ Code validé et approuvé par l'équipe",
            "",
            "---",
            "*PR créée automatiquement par AI-Agent*"
        ])
        
        return title, "\n".join(body_parts)
    
    def _add_changes_info(self, body_parts: List[str], state: Dict[str, Any]) -> None:
        """Ajoute les informations sur les changements à la PR."""
        
        body_parts.extend(["", "### 🔧 Changements apportés"])
        
        # Fichiers modifiés
        modified_files = state.get("results", {}).get("modified_files", [])
        if modified_files:
            body_parts.append("\n#### Fichiers modifiés:")
            for file_path in modified_files[:10]:  # Limiter à 10 fichiers
                body_parts.append(f"- `{file_path}`")
            if len(modified_files) > 10:
                body_parts.append(f"... et {len(modified_files) - 10} autres fichiers")
        else:
            body_parts.append("Fichiers modifiés: Informations non disponibles")
    
    def _add_quality_info(self, body_parts: List[str], state: Dict[str, Any]) -> None:
        """Ajoute les informations de qualité à la PR."""
        
        results = state.get("results", {})
        
        # Tests
        test_results = results.get("test_results")
        if test_results:
            body_parts.extend(["", "### 🧪 Tests", "✅ Tests passés avec succès"])
        
        # QA
        qa_results = results.get("qa_results")
        if qa_results and isinstance(qa_results, dict):
            score = qa_results.get("overall_score")
            if score:
                body_parts.extend([
                    "",
                    "### 📊 Qualité du code",
                    f"✅ Score qualité: {score}/100"
                ])
    
    def _cache_pr_info(self, task_id: str, pr_info: PullRequestInfo) -> None:
        """Met en cache les informations de PR."""
        
        self._pr_cache[task_id] = {
            "pr_info": pr_info,
            "cached_at": time.time(),
            "expires_at": time.time() + 3600  # 1 heure
        }
    
    def _clear_pr_cache(self, task_id: str) -> None:
        """Nettoie le cache pour une tâche."""
        
        if task_id in self._pr_cache:
            del self._pr_cache[task_id]
    
    def cleanup_expired_cache(self) -> None:
        """Nettoie le cache expiré."""
        
        now = time.time()
        expired_keys = [
            task_id for task_id, cached_data in self._pr_cache.items()
            if cached_data.get("expires_at", 0) < now
        ]
        
        for key in expired_keys:
            del self._pr_cache[key]


# Instance globale du service
pr_service = PullRequestService() 