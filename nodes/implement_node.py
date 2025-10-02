"""Nœud d'implémentation - génère et applique le code."""

from typing import Dict, Any, List
from models.state import GraphState
from anthropic import Client
from config.settings import get_settings
from tools.claude_code_tool import ClaudeCodeTool
from utils.logger import get_logger
from utils.persistence_decorator import with_persistence, log_code_generation_decorator
from utils.helpers import get_working_directory, validate_working_directory, ensure_working_directory
import os

logger = get_logger(__name__)

@with_persistence("implement_task")
@log_code_generation_decorator("claude", "claude-3-5-sonnet-20241022", "initial")
async def implement_task(state: GraphState) -> GraphState:
    """
    Nœud d'implémentation: génère et applique le code nécessaire.
    
    Ce nœud :
    1. Analyse les requirements et le contexte technique
    2. Génère un plan d'implémentation avec Claude
    3. Applique les modifications nécessaires
    4. Valide que l'implémentation répond aux critères
    
    Args:
        state: État actuel du graphe
        
    Returns:
        État mis à jour avec l'implémentation
    """
    logger.info(f"💻 Implémentation de: {state['task'].title}")

    # ✅ CORRECTION CRITIQUE: Assurer l'intégrité de l'état dès le début
    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)

    state["results"]["ai_messages"].append("Début de l'implémentation...")
    
    try:
        # Initialiser les outils nécessaires
        settings = get_settings()
        claude_tool = ClaudeCodeTool()
        anthropic_client = Client(api_key=settings.anthropic_api_key)
        task = state["task"]

        if not task:

            logger.error("❌ Aucune tâche fournie")

            return state
        


        # Initialiser results si nécessaire

        if "results" not in state:

            state["results"] = {}
        # Vérifier que l'environnement est préparé
        # ✅ AMÉLIORATION: Utiliser la fonction helper unifiée
        working_directory = get_working_directory(state)
        
        # ✅ SÉCURITÉ: Valider le répertoire avec la fonction dédiée
        if not validate_working_directory(working_directory, "implement_node"):
            # ✅ FALLBACK: Essayer de s'assurer qu'un répertoire existe
            try:
                working_directory = ensure_working_directory(state, "implement_node_")
                logger.info(f"📁 Répertoire de travail de secours créé: {working_directory}")
            except Exception as e:
                error_msg = f"Impossible de créer un répertoire de travail pour l'implémentation: {e}"
                logger.error(f"❌ {error_msg}")
                state["results"]["error_logs"].append(error_msg)
                state["results"]["ai_messages"].append(f"❌ {error_msg}")
                state["results"]["last_operation_result"] = error_msg
                state["results"]["should_continue"] = False
                state["results"]["current_status"] = "failed".lower()
                return state
        
        if not working_directory:
            error_msg = "Aucun répertoire de travail disponible pour l'implémentation"
            state["results"]["error_logs"].append(error_msg)
            state["results"]["ai_messages"].append(f"❌ {error_msg}")
            state["results"]["should_continue"] = False
            state["results"]["current_status"] = "failed".lower()
            return state
        
        # Vérifier que le répertoire existe
        if not os.path.exists(working_directory):
            error_msg = f"Répertoire de travail introuvable: {working_directory}"
            state["results"]["error_logs"].append(error_msg)
            state["results"]["ai_messages"].append(f"❌ {error_msg}")
            state["results"]["should_continue"] = False
            state["results"]["current_status"] = "failed".lower()
            return state
        
        # Initialiser code_changes si nécessaire
        if "code_changes" not in state["results"] or not isinstance(state["results"]["code_changes"], dict):
            state["results"]["code_changes"] = {}

        # Initialiser modified_files si nécessaire
        if "modified_files" not in state["results"] or not isinstance(state["results"]["modified_files"], list):
            state["results"]["modified_files"] = []
        
        # Initialiser le nouveau moteur IA multi-provider
        from tools.ai_engine_hub import ai_hub, AIRequest, TaskType
        
        claude_tool.working_directory = working_directory
        
        # 1. Analyser la structure du projet
        logger.info("📋 Analyse de la structure du projet...")
        try:
            project_analysis_text = await _analyze_project_structure(claude_tool)
            project_analysis = {
                "project_type": "detected",
                "structure": project_analysis_text,
                "files": [],
                "error": None
            }
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de l'analyse du projet: {e}")
            project_analysis = {
                "project_type": "unknown",
                "structure": "Analyse échouée",
                "files": [],
                "error": str(e)
            }
        
        logger.info(f"📊 Type de projet détecté: {project_analysis.get('project_type', 'unknown')}")
        
        # 2. Créer un prompt détaillé pour Claude
        previous_errors = state["results"].get("error_logs", []) if hasattr(state, "results") else []
        implementation_prompt = await _create_implementation_prompt(
            task, project_analysis.get("structure", "Structure non disponible"), previous_errors
        )
        
        logger.info("🤖 Génération du plan d'implémentation avec le moteur IA...")
    # Initialiser ai_messages si nécessaire
        
        # 3. Utiliser le moteur IA multi-provider pour créer un plan d'implémentation
        ai_request = AIRequest(
            prompt=implementation_prompt,
            task_type=TaskType.CODE_GENERATION,
            context={
                "task": task.dict(), 
                "project_analysis": project_analysis,
                "workflow_id": state.get("workflow_id", "unknown"),
                "task_id": task.task_id
            }
        )
        
        try:
            response = await ai_hub.generate_code(ai_request)
        except Exception as e:
            error_msg = f"Erreur lors de l'appel au moteur IA: {e}"
            state["results"]["error_logs"].append(error_msg)
            state["results"]["ai_messages"].append(f"❌ {error_msg}")
            state["results"]["should_continue"] = False
            state["results"]["current_status"] = "failed"
            return state
        
        if not response.success:
            error_msg = f"Erreur lors de la génération du plan: {response.error}"
            state["results"]["error_logs"].append(error_msg)
            state["results"]["ai_messages"].append(f"❌ {error_msg}")
            state["results"]["last_operation_result"] = error_msg
            state["results"]["should_continue"] = False
            state["results"]["current_status"] = "failed".lower()
            return state
        
        implementation_plan = response.content
        state["results"]["ai_messages"].append(f"📋 Plan généré:\n{implementation_plan[:200]}...")
        
        # 4. Exécuter le plan d'implémentation
        success = await _execute_implementation_plan(
            claude_tool, anthropic_client, implementation_plan, task, state
        )
        
        # ✅ ROBUSTESSE: Définir systématiquement tous les flags de statut
        implementation_result = _validate_implementation_result(success, state)
        
        if implementation_result["success"]:
            # Implémentation réussie
            state["results"]["ai_messages"].append("✅ Implémentation terminée avec succès")
            state["results"]["last_operation_result"] = "Implémentation réussie"
            state["results"]["implementation_success"] = True
            state["results"]["current_status"] = "implemented"
            state["results"]["implementation_metrics"] = implementation_result["metrics"]
            logger.info(f"✅ Implémentation terminée avec succès - {implementation_result['summary']}")
        else:
            # Implémentation échouée
            failure_reason = implementation_result.get("failure_reason", "Raison inconnue")
            state["results"]["ai_messages"].append(f"❌ Échec de l'implémentation: {failure_reason}")
            state["results"]["last_operation_result"] = f"Échec implémentation: {failure_reason}"
            state["results"]["implementation_success"] = False
            state["results"]["current_status"] = "implementation_failed"
            state["results"]["implementation_error_details"] = implementation_result.get("error_details", {})
            logger.error(f"❌ Échec de l'implémentation: {failure_reason}")
        
        # ✅ NOMENCLATURE: Utiliser un statut de continuation cohérent
        state["results"]["should_continue"] = True
        state["results"]["workflow_stage"] = "implementation_completed"
        
    except Exception as e:
        error_msg = f"Exception critique lors de l'implémentation: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # ✅ ROBUSTESSE: Garantir que tous les flags sont définis même en cas d'exception
        state["results"]["error_logs"].append(error_msg)
        state["results"]["ai_messages"].append(f"❌ Exception critique: {error_msg}")
        state["results"]["last_operation_result"] = error_msg
        state["results"]["implementation_success"] = False  # ✅ CRITIQUE: Toujours définir ce flag
        state["results"]["current_status"] = "implementation_exception"
        state["results"]["workflow_stage"] = "implementation_failed"
        state["results"]["should_continue"] = True
    
    logger.info("🏁 Implémentation terminée")
    return state


def _validate_implementation_result(success: bool, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valide et enrichit le résultat d'implémentation avec des métriques détaillées.
    
    Args:
        success: Résultat brut de l'implémentation
        state: État du workflow pour extraire les métriques
        
    Returns:
        Dictionnaire avec les détails de validation et métriques
    """
    result = {
        "success": False,
        "failure_reason": None,
        "error_details": {},
        "metrics": {},
        "summary": ""
    }
    
    try:
        # ✅ VALIDATION: Analyser les résultats détaillés
        results = state.get("results", {})
        
        # Compter les fichiers modifiés
        modified_files = results.get("modified_files", [])
        code_changes = results.get("code_changes", {})
        error_logs = results.get("error_logs", [])
        
        # Métriques de base
        result["metrics"] = {
            "files_modified": len(modified_files),
            "code_changes_count": len(code_changes),
            "error_count": len(error_logs),
            "has_errors": len(error_logs) > 0
        }
        
        if success:
            # Validation supplémentaire pour succès
            if len(modified_files) == 0 and len(code_changes) == 0:
                # Succès mais aucun fichier modifié - suspect
                result["success"] = False
                result["failure_reason"] = "Aucun fichier modifié détecté malgré le succès apparent"
                result["error_details"]["validation"] = "No files were actually modified"
            elif len(error_logs) > 0:
                # Succès mais avec des erreurs - succès partiel
                result["success"] = True
                result["summary"] = f"{len(modified_files)} fichier(s) modifié(s) avec {len(error_logs)} avertissement(s)"
                logger.warning(f"⚠️ Implémentation réussie mais avec {len(error_logs)} erreur(s)")
            else:
                # Succès complet
                result["success"] = True
                result["summary"] = f"{len(modified_files)} fichier(s) modifié(s) sans erreur"
        else:
            # Analyser la cause d'échec
            if len(error_logs) > 0:
                result["failure_reason"] = f"Erreurs détectées: {error_logs[-1]}"  # Dernière erreur
                result["error_details"]["last_error"] = error_logs[-1]
                result["error_details"]["total_errors"] = len(error_logs)
            else:
                result["failure_reason"] = "Échec sans erreur spécifique détectée"
                result["error_details"]["analysis"] = "No specific error found in logs"
        
        # Ajouter contexte temporel si disponible
        if "started_at" in state:
            result["metrics"]["execution_context"] = {
                "started_at": state["started_at"],
                "workflow_id": state.get("workflow_id", "unknown")
            }
            
    except Exception as e:
        logger.error(f"❌ Erreur validation résultat implémentation: {e}")
        result["success"] = False
        result["failure_reason"] = f"Erreur de validation: {str(e)}"
        result["error_details"]["validation_error"] = str(e)
    
    return result

async def _analyze_project_structure(claude_tool: ClaudeCodeTool) -> str:
    """Analyse la structure du projet pour comprendre l'architecture."""
    try:
        # Lister les fichiers principaux
        ls_result = await claude_tool._arun(action="execute_command", command="find . -type f -name '*.py' -o -name '*.js' -o -name '*.ts' -o -name '*.json' | head -20")
        
        structure_info = "Structure du projet:\n"
        if ls_result["success"]:
            structure_info += ls_result["stdout"]
        
        # Essayer de lire des fichiers de configuration importants (optionnels)
        config_files = ["package.json", "requirements.txt", "setup.py", "README.md"]
        for config_file in config_files:
            try:
                config_result = await claude_tool._arun(action="read_file", file_path=config_file, required=False)
                if config_result["success"] and config_result.get("file_exists", True):
                    structure_info += f"\n\n=== {config_file} ===\n"
                    structure_info += config_result["content"][:500] + "..."
                else:
                    # ✅ CORRECTION: Log informatif si le fichier n'existe pas
                    logger.debug(f"Fichier de configuration {config_file} non trouvé")
            except Exception:
                continue
        
        return structure_info
        
    except Exception as e:
        logger.warning(f"Impossible d'analyser la structure: {e}")
        return "Structure du projet non disponible"

async def _create_implementation_prompt(task, project_analysis: str, error_logs: List[str]) -> str:
    """Crée un prompt détaillé pour l'implémentation."""
    
    # ✅ AMÉLIORATION: Extraction intelligente des spécifications techniques
    extracted_specs = _extract_technical_specifications(task.description)
    
    prompt = f"""Tu es un développeur expert. Tu dois implémenter la tâche suivante dans un projet existant.

## TÂCHE À IMPLÉMENTER
**Titre**: {task.title}

**Description complète**: 
{task.description}

**Spécifications techniques extraites**:
{extracted_specs}

**Branche**: {task.git_branch}
**Priorité**: {task.priority}

## CONTEXTE DU PROJET
{project_analysis}

## HISTORIQUE D'ERREURS (si tentatives précédentes)
{chr(10).join(error_logs) if error_logs else "Aucune erreur précédente"}

## INSTRUCTIONS DÉTAILLÉES

1. **Analyse** d'abord le code existant pour comprendre l'architecture
2. **Identifie** les patterns et conventions utilisés dans le projet
3. **Extrait** les spécifications exactes de la description (endpoints, fonctionnalités, etc.)
4. **Planifie** les modifications nécessaires en respectant l'architecture existante
5. **Implémente** les changements de manière incrémentale

**ATTENTION SPÉCIALE**: Si la description mentionne :
- Un endpoint (ex: `/admin/costs`) → crée le router FastAPI correspondant
- Une API → implémente les endpoints REST avec documentation
- Un service → crée la classe de service appropriée
- Une base de données → génère les modèles et migrations
- Un frontend → crée les composants avec styling approprié

Réponds avec un plan d'implémentation structuré sous cette forme:

```
PLAN D'IMPLÉMENTATION

## 1. ANALYSE DE LA TÂCHE
- [Ce que tu comprends exactement de la demande]
- [Spécifications techniques identifiées]
- [Architecture cible à implémenter]

## 2. ANALYSE DU PROJET EXISTANT
- [Fichiers importants identifiés]
- [Patterns et conventions observés]
- [Architecture actuelle comprise]

## 3. MODIFICATIONS REQUISES
### Nouveaux fichiers à créer:
- [Liste des nouveaux fichiers avec leur rôle]

### Fichiers existants à modifier:
- [Liste des fichiers à modifier avec description des changements]

## 4. ÉTAPES D'EXÉCUTION DÉTAILLÉES
1. [Première étape avec commandes/modifications précises]
2. [Deuxième étape avec commandes/modifications précises]
3. [etc.]

## 5. TESTS ET VALIDATION
- [Tests ou validations à effectuer]
- [Comment vérifier que l'implémentation fonctionne]
```

**IMPORTANT**: Sois extrêmement précis dans l'extraction des spécifications. Si la description mentionne un endpoint spécifique, assure-toi de l'implémenter exactement comme demandé."""

    return prompt


def _extract_technical_specifications(description: str) -> str:
    """Extrait les spécifications techniques d'une description de tâche."""
    import re
    
    specs = []
    
    # Extraction d'endpoints
    endpoint_patterns = [
        r'endpoint\s+["`]([^"`]+)["`]',
        r'endpoint\s+([/\w-]+)',
        r'API\s+["`]([^"`]+)["`]',
        r'route\s+["`]([^"`]+)["`]',
        r'(/\w+(?:/\w+)*)',  # URLs génériques
    ]
    
    for pattern in endpoint_patterns:
        matches = re.findall(pattern, description, re.IGNORECASE)
        for match in matches:
            if match.startswith('/'):
                specs.append(f"• Endpoint à créer: {match}")
    
    # Extraction de types de fonctionnalités
    feature_patterns = [
        (r'visualiser\s+([^.]+)', "• Fonctionnalité de visualisation: {}"),
        (r'monitorer\s+([^.]+)', "• Fonctionnalité de monitoring: {}"),
        (r'tracker?\s+([^.]+)', "• Fonctionnalité de tracking: {}"),
        (r'dashboard\s+([^.]+)', "• Dashboard à créer: {}"),
        (r'rapport\s+([^.]+)', "• Rapport à générer: {}"),
        (r'afficher\s+([^.]+)', "• Affichage requis: {}"),
    ]
    
    for pattern, template in feature_patterns:
        matches = re.findall(pattern, description, re.IGNORECASE)
        for match in matches:
            specs.append(template.format(match.strip()))
    
    # Extraction de technologies/frameworks
    tech_patterns = [
        (r'FastAPI', "• Utiliser FastAPI pour les endpoints"),
        (r'React', "• Interface React requise"),
        (r'Vue', "• Interface Vue.js requise"),
        (r'PostgreSQL', "• Base de données PostgreSQL"),
        (r'MongoDB', "• Base de données MongoDB"),
        (r'REST API', "• API REST à implémenter"),
        (r'GraphQL', "• API GraphQL à implémenter"),
    ]
    
    for pattern, spec in tech_patterns:
        if re.search(pattern, description, re.IGNORECASE):
            specs.append(spec)
    
    # Extraction de données/entités
    data_patterns = [
        (r'coûts?\s+([^.]+)', "• Données de coûts: {}"),
        (r'métriques?\s+([^.]+)', "• Métriques: {}"),
        (r'statistiques?\s+([^.]+)', "• Statistiques: {}"),
        (r'logs?\s+([^.]+)', "• Logs: {}"),
    ]
    
    for pattern, template in data_patterns:
        matches = re.findall(pattern, description, re.IGNORECASE)
        for match in matches:
            specs.append(template.format(match.strip()))
    
    # Extraction de providers/services
    provider_patterns = [
        (r'provider[s]?\s+([^.]+)', "• Providers: {}"),
        (r'service[s]?\s+([^.]+)', "• Services: {}"),
        (r'(Claude|OpenAI|Anthropic)', "• Provider IA: {}"),
    ]
    
    for pattern, template in provider_patterns:
        matches = re.findall(pattern, description, re.IGNORECASE)
        for match in matches:
            specs.append(template.format(match.strip()))
    
    if not specs:
        specs.append("• Aucune spécification technique spécifique détectée")
        specs.append("• Analyse manuelle de la description requise")
    
    return "\n".join(specs)

async def _execute_implementation_plan(
    claude_tool: ClaudeCodeTool, 
    anthropic_client: Client,
    implementation_plan: str,
    task,
    state: Dict[str, Any]
) -> bool:
    """Exécute le plan d'implémentation étape par étape."""
    
    try:
        logger.info("🚀 Exécution du plan d'implémentation...")
    # Initialiser ai_messages si nécessaire
        
        # Créer un prompt pour l'exécution du plan
        execution_prompt = f"""Maintenant, exécute le plan d'implémentation suivant étape par étape.

PLAN À EXÉCUTER:
{implementation_plan}

TÂCHE:
{task.description}

Pour chaque fichier que tu dois modifier ou créer, utilise ce format exact:

```action:modify_file
file_path: chemin/vers/fichier.py
description: Description de la modification
content:
[Le contenu complet du fichier modifié]
```

OU pour exécuter des commandes:

```action:execute_command
command: la commande à exécuter
```

Commence par la première étape maintenant. N'exécute qu'une seule action à la fois."""

        response = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.1,
            messages=[{"role": "user", "content": execution_prompt}]
        )
        
        execution_steps = response.content[0].text
        
        # Parser et exécuter les actions
        success = await _parse_and_execute_actions(claude_tool, execution_steps, state)
        
        return success
        
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution du plan: {e}")
        state["results"]["error_logs"].append(f"Erreur exécution plan: {str(e)}")
        return False

async def _parse_and_execute_actions(claude_tool: ClaudeCodeTool, execution_text: str, state: Dict[str, Any]) -> bool:
    """Parse le texte d'exécution et effectue les actions."""
    
    import re
    
    success_count = 0
    total_actions = 0
    
    # Regex pour extraire les blocs d'action
    action_pattern = r'```action:(\w+)\n(.*?)\n```'
    actions = re.findall(action_pattern, execution_text, re.DOTALL)
    
    for action_type, action_content in actions:
        total_actions += 1
        logger.info(f"🔧 Exécution action: {action_type}")
    # Initialiser ai_messages si nécessaire
        
        try:
            if action_type == "modify_file":
                success = await _execute_file_modification(claude_tool, action_content, state)
            elif action_type == "execute_command":
                success = await _execute_command_action(claude_tool, action_content, state)
            else:
                logger.warning(f"Type d'action non reconnu: {action_type}")
                continue
            
            if success:
                success_count += 1
                
        except Exception as e:
            logger.error(f"Erreur lors de l'action {action_type}: {e}")
            state["results"]["error_logs"].append(f"Erreur action {action_type}: {str(e)}")
    
    # Si aucune action explicite trouvée, essayer de traiter comme modification directe
    if total_actions == 0:
        logger.info("Aucune action structurée trouvée, tentative de traitement direct...")
    # Initialiser ai_messages si nécessaire
        # Essayer d'extraire des blocs de code Python/JS
        code_blocks = re.findall(r'```(?:python|javascript|typescript)?\n(.*?)\n```', execution_text, re.DOTALL)
        
        if code_blocks:
            # Traiter le premier bloc de code comme une modification
            await _handle_direct_code_modification(claude_tool, code_blocks[0], state)
            return True
    
    success_rate = success_count / max(total_actions, 1)
    logger.info(f"📊 Actions exécutées: {success_count}/{total_actions} (taux: {success_rate:.1%})")
    # Initialiser ai_messages si nécessaire
    
    return success_rate >= 0.5  # Au moins 50% de succès

async def _execute_file_modification(claude_tool: ClaudeCodeTool, action_content: str, state: Dict[str, Any]) -> bool:
    """Exécute une modification de fichier."""
    try:
        lines = action_content.strip().split('\n')
        file_path = None
        description = ""
        content = ""
        
        content_started = False
        for line in lines:
            if line.startswith('file_path:'):
                file_path = line.split(':', 1)[1].strip()
            elif line.startswith('description:'):
                description = line.split(':', 1)[1].strip()
            elif line.startswith('content:'):
                content_started = True
            elif content_started:
                content += line + '\n'
        
        if file_path and content:
            # Créer le contexte avec workflow_id et task_id
            context = {
                "workflow_id": state.get("workflow_id", "unknown"),
                "task_id": state.get("task", {}).get("task_id", "unknown")
            }
            
            result = await claude_tool._arun(
                action="write_file",
                file_path=file_path,
                content=content.strip(),
                context=context
            )
            
            if result["success"]:
                state["results"]["code_changes"][file_path] = content.strip()
                state["results"]["modified_files"].append(file_path)
                state["results"]["ai_messages"].append(f"✅ Fichier modifié: {file_path}")
                logger.info(f"✅ Fichier modifié: {file_path}")
    # Initialiser ai_messages si nécessaire
                return True
            else:
                error = result.get("error", "Erreur inconnue")
                state["results"]["error_logs"].append(f"Échec modification {file_path}: {error}")
                logger.error(f"❌ Échec modification {file_path}: {error}")
                return False
        
        return False
        
    except Exception as e:
        logger.error(f"Erreur modification fichier: {e}")
        return False

async def _execute_command_action(claude_tool: ClaudeCodeTool, action_content: str, state: Dict[str, Any]) -> bool:
    """Exécute une commande système."""
    try:
        command = None
        for line in action_content.strip().split('\n'):
            if line.startswith('command:'):
                command = line.split(':', 1)[1].strip()
                break
        
        if command:
            result = await claude_tool._arun(action="execute_command", command=command)
            
            if result["success"]:
                state["results"]["ai_messages"].append(f"✅ Commande exécutée: {command}")
                logger.info(f"✅ Commande exécutée: {command}")
    # Initialiser ai_messages si nécessaire
                return True
            else:
                error = result.get("stderr", result.get("error", "Erreur inconnue"))
                state["results"]["error_logs"].append(f"Échec commande '{command}': {error}")
                logger.error(f"❌ Échec commande '{command}': {error}")
                return False
        
        return False
        
    except Exception as e:
        logger.error(f"Erreur exécution commande: {e}")
        return False

async def _handle_direct_code_modification(claude_tool: ClaudeCodeTool, code_content: str, state: Dict[str, Any]) -> bool:
    """Gère une modification de code directe sans structure explicite."""
    try:
        # Essayer de deviner le fichier à modifier basé sur le contenu
        if "def " in code_content or "import " in code_content:
            # Python
            filename = "main.py"  # Fichier par défaut
        elif "function " in code_content or "const " in code_content:
            # JavaScript
            filename = "main.js"
        else:
            filename = "implementation.txt"
        
        result = await claude_tool._arun(
            action="write_file",
            file_path=filename,
            content=code_content
        )
        
        if result["success"]:
            state["results"]["code_changes"][filename] = code_content
            state["results"]["modified_files"].append(filename)
            state["results"]["ai_messages"].append(f"✅ Code ajouté: {filename}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Erreur modification directe: {e}")
        return False 