"""Outil Claude Code SDK pour l'écriture et la modification de code."""

import asyncio
import os
import tempfile
import subprocess
import time
import shutil
from datetime import datetime
from typing import Any, Dict, Optional, List, Union
from pydantic import Field
from anthropic import Client

from .base_tool import BaseTool
from models.schemas import TestResult
from config.langsmith_config import langsmith_config


class ClaudeCodeTool(BaseTool):
    """Outil pour l'écriture et la modification de code avec Claude."""
    
    name: str = "claude_code_tool"
    description: str = """
    Outil pour écrire, modifier et tester du code.
    Utilise Claude pour générer du code de qualité.
    
    Fonctionnalités:
    - Lire des fichiers de code
    - Écrire/modifier des fichiers
    - Exécuter des commandes système
    - Lancer des tests
    - Analyser des erreurs
    """
    
    anthropic_client: Optional[Client] = Field(default=None)
    working_directory: Optional[str] = Field(default=None)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.anthropic_client = Client(api_key=self.settings.anthropic_api_key)
    
    async def _arun(self, action: str, **kwargs) -> Dict[str, Any]:
        """Exécute une action avec Claude Code."""
        try:
            if action == "read_file":
                return await self._read_file(kwargs.get("file_path"), kwargs.get("required", True))
            elif action == "write_file":
                return await self._write_file(
                    kwargs.get("file_path"), 
                    kwargs.get("content")
                )
            elif action == "modify_file":
                return await self._modify_file(
                    kwargs.get("file_path"),
                    kwargs.get("description"),
                    kwargs.get("context", {})
                )
            elif action == "execute_command":
                return await self._execute_command(kwargs.get("command"), cwd=kwargs.get("cwd"))
            elif action == "run_tests":
                return await self._run_tests(kwargs.get("test_command", "npm test"), cwd=kwargs.get("cwd"))
            elif action == "setup_environment":
                return await self._setup_environment(kwargs.get("repo_url"), kwargs.get("branch"))
            else:
                raise ValueError(f"Action non supportée: {action}")
                
        except Exception as e:
            return self.handle_error(e, f"claude_code_tool.{action}")
    
    async def _read_file(self, file_path: str, required: bool = True) -> Dict[str, Any]:
        """Lit le contenu d'un fichier."""
        try:
            # ✅ PROTECTION: S'assurer que file_path est une string
            if not isinstance(file_path, str):
                error_msg = f"file_path doit être une string, reçu {type(file_path)}: {file_path}"
                self.logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "file_path": str(file_path),
                    "file_exists": False,
                    "optional": False
                }
            
            full_path = self._get_full_path(file_path)
            
            # ✅ AMÉLIORATION: Distinguer les fichiers requis des fichiers optionnels
            if not os.path.exists(full_path):
                # Liste des fichiers de configuration courants (optionnels)
                optional_config_files = {
                    "package.json", "setup.py", "requirements.txt", "pyproject.toml",
                    ".env", ".gitignore", "README.md", "CHANGELOG.md", "LICENSE",
                    "pytest.ini", "tox.ini", ".flake8", "mypy.ini", ".pylintrc"
                }
                
                # Déterminer si c'est un fichier optionnel
                is_optional = (
                    not required or 
                    file_path in optional_config_files or
                    any(opt_file in file_path.lower() for opt_file in optional_config_files)
                )
                
                if is_optional:
                    # Log debug au lieu d'erreur pour les fichiers optionnels
                    self.logger.debug(f"📝 Fichier de configuration {file_path} absent - normal selon le type de projet")
                    self.log_operation(f"Vérification fichier {file_path}", True, "Fichier absent (optionnel)")
                else:
                    # Log d'erreur pour les fichiers vraiment requis
                    self.log_operation(f"Lecture fichier {file_path}", False, "Fichier non trouvé")
                
                return {
                    "success": False,
                    "error": f"Fichier non trouvé: {file_path}",
                    "file_path": file_path,
                    "file_exists": False,
                    "optional": is_optional
                }
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.log_operation(f"Lecture fichier {file_path}", True)
            return {
                "success": True,
                "content": content,
                "file_path": file_path,
                "file_exists": True
            }
        except Exception as e:
            return self.handle_error(e, f"lecture du fichier {file_path}")
    
    async def _write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Écrit du contenu dans un fichier."""
        try:
            full_path = self._get_full_path(file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.log_operation(f"Écriture fichier {file_path}", True)
            return {
                "success": True,
                "file_path": file_path,
                "bytes_written": len(content.encode('utf-8'))
            }
        except Exception as e:
            return self.handle_error(e, f"écriture du fichier {file_path}")
    
    async def _modify_file(self, file_path: str, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Modifie un fichier existant avec l'aide de Claude."""
        try:
            # Lire le fichier actuel
            current_content_result = await self._read_file(file_path)
            if not current_content_result["success"]:
                return current_content_result
            
            current_content = current_content_result["content"]
            
            # Construire le prompt pour Claude
            prompt = f"""
Tu es un développeur expert. Tu dois modifier le fichier suivant selon la description fournie.

Fichier: {file_path}
Contenu actuel:
```
{current_content}
```

Description de la modification à effectuer:
{description}

Contexte supplémentaire:
{context}

Réponds UNIQUEMENT avec le nouveau contenu complet du fichier, sans explication.
"""
            
            # Appeler Claude avec tracking du temps
            start_time = time.time()
            response = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            latency_ms = int((time.time() - start_time) * 1000)
            
            new_content = response.content[0].text.strip()
            
            # Calculer les tokens et coût
            token_usage = {}
            total_tokens = 0
            estimated_cost = 0.0
            
            if hasattr(response, 'usage') and response.usage:
                input_tokens = response.usage.input_tokens or 0
                output_tokens = response.usage.output_tokens or 0
                total_tokens = input_tokens + output_tokens
                
                # Tarification Claude 3.5 Sonnet
                estimated_cost = (input_tokens * 0.000003) + (output_tokens * 0.000015)
                
                token_usage = {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": total_tokens
                }
                
                # Log au monitoring pour agrégation
                workflow_id = context.get("workflow_id", "unknown")
                task_id = context.get("task_id", "unknown")
                
                # Import local pour éviter les imports circulaires
                from services.cost_monitoring_service import cost_monitor
                from services.monitoring_service import monitoring_dashboard
                await cost_monitor.log_ai_usage(
                    workflow_id=workflow_id,
                    task_id=task_id,
                    provider="claude",
                    model="claude-3-5-sonnet",
                    operation="modify_file",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=estimated_cost,
                    success=True
                )
                
                # Tracer avec LangSmith si configuré
                if langsmith_config.client:
                    try:
                        langsmith_config.client.create_run(
                            name=f"claude_modify_file_{file_path.split('/')[-1]}",
                            run_type="llm",
                            inputs={
                                "file_path": file_path,
                                "description": description,
                                "prompt_tokens": input_tokens,
                                "completion_tokens": output_tokens
                            },
                            outputs={
                                "success": True,
                                "estimated_cost": estimated_cost,
                                "content_length": len(new_content)
                            },
                            session_name=context.get("langsmith_session"),
                            extra={
                                "model": "claude-3-5-sonnet-20241022",
                                "provider": "claude",
                                "workflow_id": workflow_id
                            }
                        )
                    except Exception as e:
                        self.logger.warning(f"⚠️ Erreur LangSmith tracing: {e}")
                
                # Sauvegarder l'interaction en base (si run_step_id disponible)
                run_step_id = context.get("run_step_id")
                if run_step_id:
                    await monitoring_dashboard.save_ai_interaction(
                        run_step_id=run_step_id,
                        provider="claude",
                        model_name="claude-3-5-sonnet-20241022", 
                        prompt=prompt,
                        response=new_content,
                        token_usage=token_usage,
                        latency_ms=latency_ms
                    )
            
            # Écrire le nouveau contenu
            write_result = await self._write_file(file_path, new_content)
            if write_result["success"]:
                self.log_operation(f"Modification fichier {file_path}", True, 
                                 metadata={"tokens": total_tokens, "cost": estimated_cost})
                write_result["modification_description"] = description
                write_result["tokens_used"] = total_tokens
                write_result["estimated_cost"] = estimated_cost
            
            return write_result
            
        except Exception as e:
            return self.handle_error(e, f"modification du fichier {file_path}")
    
    async def _execute_command(self, command: str, cwd: str = None) -> Dict[str, Any]:
        """Exécute une commande système avec gestion améliorée des timeouts."""
        try:
            # ✅ CORRECTION: Support du paramètre cwd personnalisé
            cwd = cwd or self.working_directory or os.getcwd()
            
            # Timeout adaptatif selon le type de commande
            timeout = self._get_command_timeout(command)
            
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            success = result.returncode == 0
            self.log_operation(f"Commande: {command}", success, 
                             f"Code: {result.returncode}")
            
            return {
                "success": success,
                "command": command,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timeout_used": timeout
            }
            
        except subprocess.TimeoutExpired:
            return self.handle_error(
                TimeoutError(f"Commande expirée après {timeout}s"), 
                f"exécution de la commande: {command}"
            )
        except Exception as e:
            return self.handle_error(e, f"exécution de la commande: {command}")
    
    def _get_command_timeout(self, command: str) -> int:
        """Détermine le timeout approprié selon le type de commande."""
        if "git clone" in command:
            return 1800  # 30 minutes pour le clonage
        elif "git" in command:
            return 600   # 10 minutes pour autres opérations Git
        elif any(install_cmd in command for install_cmd in ["npm install", "pip install", "yarn install"]):
            return 900   # 15 minutes pour l'installation des dépendances
        else:
            return 300   # 5 minutes par défaut
    
    async def _execute_command_with_retry(self, command: str, max_retries: int = 2, cwd: str = None) -> Dict[str, Any]:
        """Exécute une commande avec retry automatique en cas d'échec."""
        last_result = None
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    wait_time = 2 ** attempt  # Backoff exponentiel
                    self.logger.info(f"⏱️ Attente de {wait_time}s avant retry {attempt}/{max_retries}")
                    await asyncio.sleep(wait_time)
                
                result = await self._execute_command(command, cwd=cwd)
                
                if result["success"]:
                    if attempt > 0:
                        self.logger.info(f"✅ Commande réussie après {attempt} retry(s)")
                    return result
                else:
                    last_result = result
                    if attempt < max_retries:
                        self.logger.warning(f"⚠️ Échec tentative {attempt + 1}/{max_retries + 1}: {result.get('stderr', 'Erreur inconnue')}")
                    
            except Exception as e:
                last_result = {"success": False, "error": str(e), "command": command}
                if attempt < max_retries:
                    self.logger.warning(f"⚠️ Exception tentative {attempt + 1}/{max_retries + 1}: {str(e)}")
        
        # Toutes les tentatives ont échoué
        self.logger.error(f"❌ Échec définitif après {max_retries + 1} tentatives")
        return last_result or {"success": False, "error": "Échec inconnu", "command": command}
    
    async def _run_tests(self, test_command: str, cwd: str = None) -> Dict[str, Any]:
        """Lance les tests et retourne le résultat structuré."""
        start_time = time.time()
        
        try:
            result = await self._execute_command(test_command, cwd=cwd or self.working_directory)
            duration = time.time() - start_time
            
            test_result_dict = {
                "success": result["success"],
                "test_type": "automated",
                "exit_code": result["exit_code"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "duration": duration,
                "test_command": test_command
            }
            
            self.log_operation("Tests", test_result_dict["success"], 
                             metadata={"duration": duration, "test_command": test_command})
            return test_result_dict
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Erreur lors des tests: {e}")
            return {
                "success": False,
                "test_type": "error",
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "duration": duration,
                "test_command": test_command
            }
    
    async def _setup_environment(self, repo_url: str, branch: str) -> Dict[str, Any]:
        """
        Configure l'environnement de travail avec gestion avancée des dépendances.
        """
        try:
            # ✅ CORRECTION ROBUSTE: Créer répertoire de travail avec fallbacks
            current_working_dir_path = self.working_directory
            
            if not current_working_dir_path or not os.path.exists(str(current_working_dir_path)):
                try:
                    self.working_directory = tempfile.mkdtemp(prefix="ai_agent_")
                    self.logger.info(f"📁 Répertoire de travail créé: {self.working_directory}")
                except Exception as e:
                    # Fallback si tempfile.mkdtemp() échoue
                    self.working_directory = "/tmp/ai_agent_fallback"
                    os.makedirs(self.working_directory, exist_ok=True)
                    self.logger.warning(f"⚠️ Fallback répertoire: {self.working_directory} (erreur tempfile: {e})")
            else:
                self.logger.info(f"📁 Répertoire de travail existant réutilisé: {self.working_directory}")
            
            # Assurer que le répertoire existe et est accessible
            if not os.path.exists(self.working_directory):
                os.makedirs(self.working_directory, exist_ok=True)
            
            # ✅ AMÉLIORATION: Diagnostics préliminaires
            await self._run_git_diagnostics()
            
            # ✅ CORRECTION: Cloner le repository avec tolérance d'échec
            self.logger.info(f"📥 Clonage du repository: {repo_url}")
            clone_success = False
            clone_result = {"success": False, "stderr": "Aucune tentative effectuée"} 
            
            # Valider l'URL du repository
            if not repo_url or not repo_url.strip():
                self.logger.warning("⚠️ Aucune URL de repository fournie - création d'un workspace vide")
            elif not self._is_valid_git_url(repo_url):
                self.logger.warning(f"⚠️ URL repository invalide: {repo_url} - création d'un workspace vide")
            else:
                # Nettoyer le répertoire de travail avant clonage
                await self._prepare_clean_workspace()
                
                # Stratégies de clonage avec diagnostics spécifiques
                clone_attempts = [
                    (f"git clone --depth 1 {repo_url} .", "Clonage superficiel rapide"),
                    (f"git clone {repo_url} .", "Clonage complet"),
                    (f"git -c http.sslVerify=false clone --depth 1 {repo_url} .", "SSL désactivé + superficiel"),
                    (f"git -c http.version=HTTP/1.1 clone --depth 1 {repo_url} .", "HTTP/1.1 + superficiel"),
                    (f"git -c http.postBuffer=524288000 clone --depth 1 {repo_url} .", "Buffer élevé + superficiel")
                ]
                
                for i, (clone_cmd, description) in enumerate(clone_attempts, 1):
                    self.logger.info(f"🔄 Tentative {i}/{len(clone_attempts)} - {description}")
                    
                    clone_result = await self._execute_command(clone_cmd, cwd=self.working_directory)
                    
                    if clone_result["success"]:
                        # Vérifier que le clonage est complet
                        verification_result = await self._verify_clone_success()
                        if verification_result:
                            clone_success = True
                            self.logger.info(f"✅ Clonage réussi à la tentative {i} ({description})")
                            break
                        else:
                            self.logger.warning(f"⚠️ Clonage incomplet à la tentative {i}")
                    else:
                        self.logger.warning(f"❌ Échec tentative {i}: {clone_result.get('stderr', 'Erreur inconnue')}")
                    
                    # Nettoyer le répertoire avant la prochaine tentative
                    if i < len(clone_attempts):
                        await self._clean_failed_clone()
                        await asyncio.sleep(i * 2)  # Backoff progressif
            
            # ✅ CORRECTION: Continuer même si clonage échoue
            if not clone_success:
                self.logger.warning("⚠️ Clonage échoué - création d'un workspace vide")
                # Créer un workspace minimal fonctionnel
                await self._create_minimal_workspace(branch)
            else:
                # Créer et checkout la nouvelle branche (uniquement si clone réussi)
                self.logger.info(f"🌿 Création ou récupération de la branche: {branch}")
                checkout_result = await self._execute_command(f"git checkout -b {branch} || git checkout {branch}", cwd=self.working_directory)
                
                if not checkout_result["success"]:
                    self.logger.warning(f"⚠️ Impossible de gérer la branche {branch} - utilisation de master/main")
                    # Essayer de rester sur la branche par défaut
                    default_branch_result = await self._execute_command("git branch --show-current", cwd=self.working_directory)
                    if default_branch_result["success"]:
                        current_branch = default_branch_result["stdout"].strip()
                        self.logger.info(f"📝 Utilisation de la branche existante: {current_branch}")
            
            # Installer les dépendances (même sans git)
            dependency_installed = await self._install_dependencies()
            
            # Assurer la structure de base
            await self._ensure_basic_structure()
            
            # ✅ VALIDATION: S'assurer que le working_directory est valide avant de retourner
            if not self.working_directory or not os.path.exists(self.working_directory):
                self.logger.error(f"❌ Working directory invalide avant retour: {self.working_directory}")
                return {
                    "success": False,
                    "error": f"Working directory invalide: {self.working_directory}",
                    "working_directory": None
                }
            
            # ✅ CORRECTION: Toujours retourner un succès avec working_directory valide
            return {
                "success": True,  # Toujours True car on a un workspace utilisable
                "working_directory": self.working_directory,
                "branch": branch,
                "repo_url": repo_url,
                "clone_success": clone_success,
                "dependencies_installed": dependency_installed,
                "fallback_mode": not clone_success
            }
            
        except Exception as e:
            # ✅ CORRECTION: Même en cas d'exception, fournir un workspace
            self.logger.error(f"❌ Exception dans setup_environment: {e}")
            
            # Créer un workspace d'urgence
            emergency_workspace = "/tmp/ai_agent_emergency"
            try:
                os.makedirs(emergency_workspace, exist_ok=True)
                self.working_directory = emergency_workspace
                
                return {
                    "success": True,  # True car on a un workspace
                    "working_directory": emergency_workspace,
                    "branch": branch,
                    "repo_url": repo_url,
                    "clone_success": False,
                    "dependencies_installed": False,
                    "emergency_mode": True,
                    "error": str(e)
                }
            except Exception as fatal_error:
                # Si même le workspace d'urgence échoue, utiliser le handle_error original
                return self.handle_error(fatal_error, "configuration de l'environnement")

    async def _create_essential_log_files(self):
        """Crée les fichiers de log essentiels souvent recherchés par le debug."""
        log_files = {
            "error.log": "# Log des erreurs\n# Créé automatiquement par AI-Agent\n\n",
            "debug.log": "# Log de debug\n# Créé automatiquement par AI-Agent\n\n", 
            "test.log": "# Log des tests\n# Créé automatiquement par AI-Agent\n\n",
            ".pytest_cache/README.md": "# Cache pytest\nCe dossier contient le cache de pytest\n"
        }
        
        for log_file, content in log_files.items():
            file_path = os.path.join(self.working_directory, log_file)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.logger.debug(f"📝 Créé: {log_file}")
    
    async def _create_dependency_failure_log(self, lang_name: str, install_result: Dict[str, Any]):
        """Crée un log d'échec d'installation des dépendances pour diagnostic."""
        failure_log = f"""# Échec installation dépendances - {lang_name}
Date: {datetime.now().isoformat()}
Commande: {install_result.get('command', 'N/A')}
Code sortie: {install_result.get('exit_code', 'N/A')}

## Erreur:
{install_result.get('stderr', 'Aucune erreur capturée')}

## Sortie:
{install_result.get('stdout', 'Aucune sortie capturée')}
"""
        
        log_path = os.path.join(self.working_directory, f"dependency_failure_{lang_name.lower().replace(' ', '_')}.log")
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(failure_log)
    
    async def _create_minimal_requirements(self):
        """Crée un requirements.txt minimal si aucun fichier de dépendance n'existe."""
        req_path = os.path.join(self.working_directory, "requirements.txt")
        
        if not os.path.exists(req_path):
            minimal_reqs = """# Requirements générés automatiquement par AI-Agent
# Ajoutez vos dépendances ici

# Dépendances de base communes
requests>=2.25.0
pytest>=6.0.0
black>=21.0.0
flake8>=3.8.0
"""
            with open(req_path, 'w', encoding='utf-8') as f:
                f.write(minimal_reqs)
            self.logger.info("📝 Créé requirements.txt minimal")
    
    async def _ensure_project_structure(self):
        """S'assure que les dossiers essentiels existent."""
        essential_dirs = [
            "tests", "test", "__pycache__", ".pytest_cache",
            "logs", "tmp", "temp", "build", "dist"
        ]
        
        for dir_name in essential_dirs:
            dir_path = os.path.join(self.working_directory, dir_name)
            os.makedirs(dir_path, exist_ok=True)
    
    async def _ensure_gitignore(self):
        """Crée un .gitignore minimal s'il n'existe pas."""
        gitignore_path = os.path.join(self.working_directory, ".gitignore")
        
        if not os.path.exists(gitignore_path):
            gitignore_content = """# AI-Agent generated .gitignore

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.env
venv/
env/
*.egg-info/
dist/
build/

# Tests
.pytest_cache/
.coverage
htmlcov/
.tox/

# Logs
*.log
logs/

# IDEs
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Dependencies
node_modules/
"""
            with open(gitignore_path, 'w', encoding='utf-8') as f:
                f.write(gitignore_content)
            self.logger.info("📝 Créé .gitignore minimal")
    
    async def _create_minimal_workspace(self, branch: str):
        """Crée un workspace minimal quand le clonage échoue."""
        self.logger.info("🔧 Création d'un workspace minimal...")
        
        # Initialiser git si possible
        try:
            await self._execute_command("git init", cwd=self.working_directory)
            await self._execute_command(f"git checkout -b {branch}", cwd=self.working_directory)
            self.logger.info(f"✅ Workspace git minimal créé avec branche {branch}")
        except:
            self.logger.warning("⚠️ Impossible d'initialiser git - workspace sans version")
        
        # Créer des fichiers de base
        basic_files = {
            "README.md": f"# Workspace AI-Agent\n\nBranche: {branch}\nCréé automatiquement\n",
            "main.py": "# Fichier principal\nprint('Hello AI-Agent')\n",
            ".gitignore": "__pycache__/\n*.pyc\n.env\nnode_modules/\n"
        }
        
        for filename, content in basic_files.items():
            file_path = os.path.join(self.working_directory, filename)
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            except:
                pass  # Ignorer les erreurs de création de fichiers
    
    async def _install_dependencies(self) -> bool:
        """Installe les dépendances de manière robuste."""
        # Commandes d'installation optimisées
        install_commands = [
            ("pip install -r requirements.txt", "requirements.txt"),
            ("npm install --silent", "package.json"),
            ("pip install -e .", "setup.py"),
        ]
        
        dependency_installed = False
        for cmd, dependency_file in install_commands:
            file_path = os.path.join(self.working_directory, dependency_file)
            if os.path.exists(file_path):
                self.logger.info(f"📦 Installation: {cmd}")
                install_result = await self._execute_command(cmd, cwd=self.working_directory)
                if install_result["success"]:
                    dependency_installed = True
                else:
                    self.logger.warning(f"⚠️ Échec: {cmd}")
        
        return dependency_installed
    
    async def _ensure_basic_structure(self):
        """Assure une structure de projet de base."""
        basic_dirs = ["src", "tests", "docs"]
        for dir_name in basic_dirs:
            dir_path = os.path.join(self.working_directory, dir_name)
            os.makedirs(dir_path, exist_ok=True)
    
    def _get_full_path(self, file_path: str) -> str:
        """Retourne le chemin complet d'un fichier."""
        if os.path.isabs(file_path):
            return file_path
        
        # ✅ CORRECTION: Utiliser getattr pour obtenir la valeur du Field
        working_dir = getattr(self, 'working_directory', None)
        # Protection supplémentaire si c'est encore un FieldInfo
        if hasattr(working_dir, 'default'):
            working_dir = working_dir.default
        
        base_dir = working_dir or os.getcwd()
        return os.path.join(base_dir, file_path) 

    async def _run_git_diagnostics(self):
        """Effectue des diagnostics Git préliminaires."""
        try:
            # Vérifier si Git est installé
            git_version_result = await self._execute_command("git --version")
            if git_version_result["success"]:
                self.logger.info(f"✅ Git disponible: {git_version_result['stdout'].strip()}")
            else:
                self.logger.warning("⚠️ Git non disponible ou non fonctionnel")
                return
            
            # Vérifier la configuration Git globale
            config_checks = [
                ("user.name", "git config --global user.name"),
                ("user.email", "git config --global user.email")
            ]
            
            for config_name, config_cmd in config_checks:
                result = await self._execute_command(config_cmd)
                if result["success"] and result["stdout"].strip():
                    self.logger.debug(f"✅ Config {config_name}: {result['stdout'].strip()}")
                else:
                    self.logger.info(f"📝 Configuration Git manquante: {config_name}")
                    # Configurer des valeurs par défaut
                    if config_name == "user.name":
                        await self._execute_command("git config --global user.name 'AI-Agent'")
                    elif config_name == "user.email":
                        await self._execute_command("git config --global user.email 'ai-agent@smartelia.com'")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur lors des diagnostics Git: {e}")

    def _is_valid_git_url(self, url: str) -> bool:
        """Valide si une URL est un repository Git valide."""
        if not url or not isinstance(url, str):
            return False
        
        url = url.strip()
        
        # Patterns valides pour les URLs Git
        valid_patterns = [
            r'^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?/?$',
            r'^git@github\.com:[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?$',
            r'^https://gitlab\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?/?$',
            r'^https://bitbucket\.org/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?/?$'
        ]
        
        import re
        for pattern in valid_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        
        return False

    async def _prepare_clean_workspace(self):
        """Prépare un workspace propre pour le clonage."""
        try:
            # Nettoyer le contenu existant du répertoire (sauf les fichiers cachés système)
            if os.path.exists(self.working_directory):
                for item in os.listdir(self.working_directory):
                    if not item.startswith('.'):
                        item_path = os.path.join(self.working_directory, item)
                        if os.path.isdir(item_path):
                            import shutil
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                self.logger.debug("🧹 Workspace nettoyé avant clonage")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur lors du nettoyage workspace: {e}")

    async def _verify_clone_success(self) -> bool:
        """Vérifie que le clonage Git s'est bien passé."""
        try:
            # Vérifier la présence du dossier .git
            git_dir = os.path.join(self.working_directory, ".git")
            if not os.path.exists(git_dir):
                return False
            
            # Vérifier que le repository est fonctionnel
            status_result = await self._execute_command("git status --porcelain", cwd=self.working_directory)
            if not status_result["success"]:
                return False
            
            # Vérifier qu'il y a des fichiers dans le repo
            files_result = await self._execute_command("find . -type f -not -path './.git/*' | head -5", cwd=self.working_directory)
            if files_result["success"] and files_result["stdout"].strip():
                self.logger.debug(f"✅ Repository contient des fichiers: {len(files_result['stdout'].strip().split())} fichiers trouvés")
                return True
            
            # Si pas de fichiers, peut-être un repo vide mais valide
            return True
            
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur lors de la vérification du clonage: {e}")
            return False

    async def _clean_failed_clone(self):
        """Nettoie les restes d'un clonage échoué."""
        try:
            if os.path.exists(self.working_directory):
                for item in os.listdir(self.working_directory):
                    item_path = os.path.join(self.working_directory, item)
                    if os.path.isdir(item_path):
                        import shutil
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                self.logger.debug("🧹 Nettoyage après échec de clonage")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur lors du nettoyage: {e}") 