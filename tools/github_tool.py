"""Outil GitHub pour la gestion des Pull Requests."""

import os
import subprocess
from datetime import datetime
from typing import Any, Dict, Optional
from github import Github, GithubException
from pydantic import Field

from .base_tool import BaseTool
from models.schemas import GitOperationResult, PullRequestInfo
from config.langsmith_config import langsmith_config


class GitHubTool(BaseTool):
    """Outil pour interagir avec l'API GitHub."""

    name: str = "github_tool"
    description: str = """
    Outil pour interagir avec GitHub.

    Fonctionnalités:
    - Créer des Pull Requests
    - Pousser des branches
    - Ajouter des commentaires
    - Gérer les labels et assignations
    """

    github_client: Optional[Github] = Field(default=None)
    repository: Optional[Any] = Field(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.github_client = Github(self.settings.github_token)

    async def _arun(self, action: str, **kwargs) -> Dict[str, Any]:
        """Exécute une action GitHub."""
        try:
            if action == "create_pull_request":
                return await self._create_pull_request(
                    repo_url=kwargs.get("repo_url"),
                    title=kwargs.get("title"),
                    body=kwargs.get("body"),
                    head_branch=kwargs.get("head_branch"),
                    base_branch=kwargs.get("base_branch", "main")
                )
            elif action == "push_branch":
                git_result = await self._push_branch(
                    repo_url=kwargs.get("repo_url"),
                    branch=kwargs.get("branch"),
                    working_directory=kwargs.get("working_directory")
                )
                # Convertir GitOperationResult en dictionnaire
                return {
                    "success": git_result.success,
                    "message": git_result.message,
                    "branch": git_result.branch,
                    "commit_hash": git_result.commit_hash,
                    "error": git_result.error
                }
            elif action == "add_comment":
                return await self._add_comment(
                    repo_url=kwargs.get("repo_url"),
                    pr_number=kwargs.get("pr_number"),
                    comment=kwargs.get("comment")
                )
            else:
                raise ValueError(f"Action non supportée: {action}")

        except Exception as e:
            return self.handle_error(e, f"github_tool.{action}")

    async def _create_pull_request(self, repo_url: str, title: str, body: str,
                                   head_branch: str, base_branch: str = "main") -> Dict[str, Any]:
        """Crée une Pull Request sur GitHub."""
        try:
            # Extraire le nom du repository depuis l'URL
            repo_name = self._extract_repo_name(repo_url)
            self.logger.info(f"🔍 Tentative d'accès au repository: {repo_name}")

            # Vérifier l'accès au repository
            try:
                repo = self.github_client.get_repo(repo_name)
            except GithubException as e:
                if e.status == 404:
                    return {
                        "success": False,
                        "error": f"Repository {repo_name} non trouvé ou token sans permissions (404). Vérifiez GITHUB_TOKEN et permissions."
                    }
                elif e.status == 401:
                    return {
                        "success": False,
                        "error": "Token GitHub invalide ou expiré (401). Vérifiez GITHUB_TOKEN."
                    }
                raise

            self.logger.info(f"✅ Repository accessible: {repo_name}")

            # Vérifier que la branche base existe
            try:
                repo.get_branch(base_branch)
            except GithubException as e:
                if e.status == 404:
                    # Essayer avec 'master' si 'main' n'existe pas
                    if base_branch == "main":
                        try:
                            repo.get_branch("master")
                            base_branch = "master"
                            self.logger.info(f"✅ Branche 'master' trouvée, utilisation comme base")
                        except GithubException:
                            return {
                                "success": False,
                                "error": f"Aucune branche base trouvée ('main' ou 'master')"
                            }
                    else:
                        return {
                            "success": False,
                            "error": f"Branche de base '{base_branch}' inexistante. Vérifiez DEFAULT_BASE_BRANCH."
                        }
                else:
                    raise

            # Vérifier que la branche head existe - avec retry et attente
            max_retries = 3
            retry_delay = 5  # secondes
            
            for attempt in range(max_retries):
                try:
                    repo.get_branch(head_branch)
                    self.logger.info(f"✅ Branche {head_branch} trouvée sur GitHub")
                    break
                except GithubException as e:
                    if e.status == 404:
                        if attempt < max_retries - 1:
                            self.logger.warning(f"⚠️ Branche {head_branch} pas encore visible (tentative {attempt + 1}/{max_retries}), attente {retry_delay}s...")
                            import asyncio
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            return {
                                "success": False,
                                "error": f"La branche {head_branch} n'existe pas sur GitHub après {max_retries} tentatives. Vérifiez que le push a réussi."
                            }
                    else:
                        raise

            # Construire la référence de branche correcte
            # Pour les PR, la branche head doit être au format "owner:branch" si c'est un fork
            # ou juste "branch" si c'est le même repository
            head_ref = head_branch
            
            # Créer la Pull Request
            self.logger.info(f"🔨 Création PR: {head_ref} → {base_branch}")
            pr = repo.create_pull(
                title=title,
                body=body,
                head=head_ref,
                base=base_branch
            )

            pr_info = PullRequestInfo(
                number=pr.number,
                title=pr.title,
                url=pr.html_url,
                branch=head_branch,
                base_branch=base_branch,
                status="open",
                created_at=datetime.now()
            )

            self.log_operation(f"Création PR #{pr.number}", True, pr.html_url)

            # Tracer avec LangSmith si configuré
            if langsmith_config.client:
                try:
                    langsmith_config.client.create_run(
                        name=f"github_create_pr_{pr.number}",
                        run_type="tool",
                        inputs={
                            "repo_url": repo_url,
                            "title": title,
                            "head_branch": head_branch,
                            "base_branch": base_branch
                        },
                        outputs={
                            "success": True,
                            "number": pr.number,
                            "url": pr.html_url
                        },
                        extra={
                            "tool": "github",
                            "operation": "create_pull_request",
                            "repo_name": repo_name
                        }
                    )
                except Exception as e:
                    self.logger.warning(f"⚠️ Erreur LangSmith tracing: {e}")

            return {
                "success": True,
                "pr_info": pr_info.dict(),
                "url": pr.html_url,
                "number": pr.number
            }

        except GithubException as e:
            if e.status == 422 and "pull request already exists" in str(e):
                # PR existe déjà, essayer de la récupérer
                try:
                    existing_prs = repo.get_pulls(
                        state="open",
                        head=f"{repo.owner.login}:{head_branch}",
                        base=base_branch
                    )
                    if existing_prs.totalCount > 0:
                        existing_pr = existing_prs[0]
                        pr_info = PullRequestInfo(
                            number=existing_pr.number,
                            title=existing_pr.title,
                            url=existing_pr.html_url,
                            branch=head_branch,
                            base_branch=base_branch,
                            status=existing_pr.state,
                            created_at=datetime.now()
                        )

                        self.log_operation(f"PR existante trouvée #{existing_pr.number}", True)
                        return {
                            "success": True,
                            "pr_info": pr_info.dict(),
                            "url": existing_pr.html_url,
                            "number": existing_pr.number,
                            "message": "Pull Request existante utilisée"
                        }
                except Exception:
                    pass
            elif e.status == 404:
                # Erreur 404 spécifique avec contexte détaillé
                return {
                    "success": False,
                    "error": f"Erreur 404 lors de création PR: {str(e)}. Vérifiez que la branche '{head_branch}' existe sur GitHub et que vous avez les permissions pour créer une PR sur ce repository.",
                    "operation": "création de la Pull Request",
                    "details": {
                        "repo_url": repo_url,
                        "head_branch": head_branch,
                        "base_branch": base_branch,
                        "status_code": 404
                    }
                }

            return self.handle_error(e, "création de la Pull Request")
        except Exception as e:
            return self.handle_error(e, "création de la Pull Request")

    async def _push_branch(self, working_directory: str, branch: str) -> GitOperationResult:
        """Pousse une branche vers GitHub."""
        try:
            # Validation des paramètres
            if not working_directory or not os.path.exists(working_directory):
                error_msg = f"Répertoire de travail invalide: {working_directory}"
                self.logger.error(f"❌ {error_msg}")
                return GitOperationResult(
                    success=False,
                    message=error_msg,
                    branch=branch,
                    error=error_msg
                )

            if not branch:
                error_msg = "Nom de branche manquant"
                self.logger.error(f"❌ {error_msg}")
                return GitOperationResult(
                    success=False,
                    message=error_msg,
                    branch=branch,
                    error=error_msg
                )

            # Vérifier que c'est un dépôt Git
            git_dir = os.path.join(working_directory, '.git')
            if not os.path.exists(git_dir):
                error_msg = f"Le répertoire {working_directory} n'est pas un dépôt Git (pas de .git)"
                self.logger.error(f"❌ {error_msg}")
                return GitOperationResult(
                    success=False,
                    message=error_msg,
                    branch=branch,
                    error=error_msg
                )

            # Changer vers le répertoire de travail
            original_cwd = os.getcwd()
            self.logger.info(f"🔄 Changement de répertoire: {original_cwd} → {working_directory}")
            os.chdir(working_directory)

            try:
                # Configurer Git avec le token pour l'authentification
                github_token = self.settings.github_token
                if github_token:
                    # Configurer le helper de credentials pour utiliser le token
                    subprocess.run(
                        ["git", "config", "credential.helper", "store"],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                
                # Vérifier le statut git avant de commencer
                status_result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                if not status_result.stdout.strip():
                    self.logger.warning("⚠️ Aucun changement détecté dans le repository")
                
                # Ajouter tous les fichiers modifiés
                add_result = subprocess.run(
                    ["git", "add", "."],
                    capture_output=True,
                    text=True,
                    check=True
                )

                # Vérifier s'il y a quelque chose à committer
                status_after_add = subprocess.run(
                    ["git", "diff", "--cached", "--name-only"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                if not status_after_add.stdout.strip():
                    self.logger.warning("⚠️ Aucun fichier à committer après git add")

                # Committer les changements
                commit_result = subprocess.run(
                    ["git", "commit", "-m", f"Implémentation automatique - {branch}", "--allow-empty"],
                    capture_output=True,
                    text=True,
                    check=True
                )

                # Pousser la branche avec authentification
                push_command = ["git", "push", "origin", branch]
                
                # Si on a un token, modifier l'URL pour inclure l'authentification
                if github_token:
                    # Récupérer l'URL remote actuelle
                    remote_result = subprocess.run(
                        ["git", "remote", "get-url", "origin"],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    
                    remote_url = remote_result.stdout.strip()
                    if remote_url.startswith("https://github.com/"):
                        # Ajouter le token à l'URL
                        auth_url = remote_url.replace("https://github.com/", f"https://{github_token}@github.com/")
                        subprocess.run(
                            ["git", "remote", "set-url", "origin", auth_url],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                
                push_result = subprocess.run(
                    push_command,
                    capture_output=True,
                    text=True,
                    check=True
                )

                # Récupérer le hash du commit
                commit_hash_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                commit_hash = commit_hash_result.stdout.strip()

                git_result = GitOperationResult(
                    success=True,
                    message=f"Branche {branch} poussée avec succès",
                    branch=branch,
                    commit_hash=commit_hash
                )

                self.log_operation(f"Push branche {branch}", True, commit_hash)
                return git_result

            finally:
                os.chdir(original_cwd)

        except subprocess.CalledProcessError as e:
            error_msg = f"Erreur Git: {e.stderr if e.stderr else e.stdout}"
            self.logger.error(f"❌ {error_msg}")
            self.logger.error(f"❌ Commande échouée: {' '.join(e.cmd)}")
            return GitOperationResult(
                success=False,
                message=error_msg,
                branch=branch,
                error=error_msg
            )
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"❌ Erreur inattendue lors du push: {error_msg}")
            return GitOperationResult(
                success=False,
                message=error_msg,
                branch=branch,
                error=error_msg
            )

    async def _add_comment(self, repo_url: str, pr_number: int, comment: str) -> Dict[str, Any]:
        """Ajoute un commentaire à une Pull Request."""
        try:
            repo_name = self._extract_repo_name(repo_url)
            repo = self.github_client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)

            comment_obj = pr.create_issue_comment(comment)

            self.log_operation(f"Commentaire ajouté PR #{pr_number}", True)

            return {
                "success": True,
                "comment_id": comment_obj.id,
                "comment_url": comment_obj.html_url
            }

        except Exception as e:
            return self.handle_error(e, f"ajout de commentaire à la PR #{pr_number}")

    def _extract_repo_name(self, repo_url: str) -> str:
        """Extrait le nom du repository depuis une URL GitHub."""
        # Gérer différents formats d'URL
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]

        if 'github.com/' in repo_url:
            # Extraire la partie après github.com/
            parts = repo_url.split('github.com/')[-1]
            return parts
        else:
            raise ValueError(f"URL de repository invalide: {repo_url}")

    def cleanup(self):
        """Nettoie les ressources."""
        if hasattr(self, 'github_client'):
            # GitHub API n'a pas besoin de nettoyage explicite
            pass
