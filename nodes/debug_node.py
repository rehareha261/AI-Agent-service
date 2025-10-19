"""Nœud de debug - analyse et corrige les erreurs de tests."""

from typing import Dict, Any, Tuple
from models.state import GraphState

from tools.claude_code_tool import ClaudeCodeTool
from utils.logger import get_logger
from utils.helpers import get_working_directory, validate_working_directory, ensure_working_directory
from anthropic import Client
from openai import AsyncOpenAI
from config.settings import get_settings
from utils.persistence_decorator import with_persistence, log_code_generation_decorator

logger = get_logger(__name__)

# Flag pour activer/désactiver la classification LangChain (Phase 3)
USE_LANGCHAIN_ERROR_CLASSIFICATION = True


async def _call_llm_with_fallback(anthropic_client: Client, openai_client: AsyncOpenAI, prompt: str, max_tokens: int = 4000) -> Tuple[str, str]:
    """
    Appelle le LLM avec fallback automatique Anthropic → OpenAI.
    
    Returns:
        Tuple[content, provider_used]
    """
    # Tentative 1: Anthropic
    try:
        logger.info("🚀 Tentative avec Anthropic...")
        response = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.content[0].text
        logger.info("✅ Anthropic réussi")
        return content, "anthropic"
    except Exception as e:
        logger.warning(f"⚠️ Anthropic échoué: {e}")
        
        # Tentative 2: OpenAI fallback
        if openai_client:
            try:
                logger.info("🔄 Fallback vers OpenAI...")
                response = await openai_client.chat.completions.create(
                    model="gpt-4o",
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )
                content = response.choices[0].message.content
                logger.info("✅ OpenAI fallback réussi")
                return content, "openai"
            except Exception as e2:
                logger.error(f"❌ OpenAI fallback échoué: {e2}")
                raise Exception(f"Anthropic et OpenAI ont échoué. Anthropic: {e}, OpenAI: {e2}")
        else:
            logger.error("❌ Pas de fallback OpenAI disponible")
            raise Exception(f"Anthropic échoué et pas de fallback OpenAI: {e}")

@with_persistence("debug_code")
@log_code_generation_decorator("claude", "claude-3-5-sonnet-20241022", "debug")
async def debug_code(state: GraphState) -> GraphState:
    """
    Nœud de debug: analyse et corrige les erreurs de code.
    
    Ce nœud :
    1. Analyse les erreurs de tests
    2. Identifie les causes racines
    3. Génère des corrections avec Claude
    4. Applique les corrections automatiquement
    
    Args:
        state: État actuel du graphe
        
    Returns:
        État mis à jour avec les corrections
    """
    logger.info(f"🔧 Debug du code pour: {state['task'].title}")
    
    # ✅ CORRECTION CRITIQUE: Assurer l'intégrité de l'état dès le début
    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)

    state["results"]["ai_messages"].append("Début du debug...")
    
    state["results"]["current_status"] = "DEBUGGING".lower()
    
    # Le compteur est maintenant géré dans _should_debug(), ne pas incrémenter ici
    current_attempt = state["results"].get("debug_attempts", 1)
    state["results"]["ai_messages"].append(f"Début du debug (tentative {current_attempt}/3)...")
    
    try:
        # Vérifier qu'il y a des erreurs à débugger
        if not state["results"]["test_results"]:
            error_msg = "Aucun résultat de test disponible pour le debug"
            state["results"]["error_logs"].append(error_msg)
            state["results"]["ai_messages"].append(f"❌ {error_msg}")
            state["results"]["should_continue"] = False
            state["results"]["current_status"] = "failed".lower()
            return state
        
        # Prendre le dernier résultat de test (le plus récent)
        latest_test_result = state["results"]["test_results"][-1]
        
        # Utiliser .get() pour accéder à 'success' puisque c'est maintenant un dictionnaire
        if latest_test_result.get("success", False):
            # Tests déjà réussis, pas besoin de debug
            state["results"]["ai_messages"].append("✅ Tests déjà réussis, pas de debug nécessaire")
            state["results"]["should_continue"] = True
            return state
        
        # ✅ CORRECTION ROBUSTE: Récupérer le répertoire de travail de manière sécurisée
        working_directory = get_working_directory(state)
        
        if not validate_working_directory(working_directory, "debug_node"):
            logger.warning("⚠️ Répertoire de travail invalide, tentative de récupération...")
            try:
                working_directory = ensure_working_directory(state, "debug_node_")
                logger.info(f"📁 Répertoire de travail de secours créé: {working_directory}")
            except Exception as e:
                error_msg = f"Impossible de créer un répertoire de travail pour le debug: {e}"
                logger.error(f"❌ {error_msg}")
                state["results"]["error_logs"].append(error_msg)
                state["results"]["ai_messages"].append(f"❌ {error_msg}")
                state["results"]["current_status"] = "failed"
                return state
        
        # Initialiser les outils avec le répertoire validé
        claude_tool = ClaudeCodeTool()
        claude_tool.working_directory = working_directory
        
        settings = get_settings()
        anthropic_client = Client(api_key=settings.anthropic_api_key)
        # Initialiser OpenAI client pour fallback
        openai_client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        
        # 1. Analyser l'erreur en détail
        logger.info("🔍 Analyse détaillée de l'erreur...")
    # Initialiser ai_messages si nécessaire
        error_analysis = await _analyze_error_in_detail(
            latest_test_result, state, claude_tool
        )
        
        # 1.5. PHASE 3: Classification et regroupement des erreurs (optionnel)
        error_classification = None
        if USE_LANGCHAIN_ERROR_CLASSIFICATION:
            try:
                logger.info("🔗 Classification des erreurs avec LangChain...")
                
                from ai.chains.debug_error_classification_chain import (
                    classify_debug_errors,
                    extract_classification_metrics,
                    get_priority_ordered_groups
                )
                
                # Récupérer les logs et traces
                test_output = latest_test_result.get("output", "")
                stack_trace = latest_test_result.get("stack_trace", "")
                
                # Classifier les erreurs
                error_classification = await classify_debug_errors(
                    test_logs=test_output,
                    stack_traces=stack_trace,
                    recent_diff=None,  # TODO: Récupérer le diff si disponible
                    modified_files=list(state["results"].get("code_changes", {}).keys()),
                    additional_context={
                        "task_id": state["task"].task_id,
                        "debug_attempt": current_attempt
                    },
                    provider="anthropic",
                    fallback_to_openai=True
                )
                
                # Extraire les métriques
                metrics = extract_classification_metrics(error_classification)
                
                logger.info(
                    f"✅ Classification terminée: "
                    f"{metrics['total_errors']} erreurs → {metrics['total_groups']} groupes "
                    f"(réduction: {metrics['reduction_percentage']:.1f}%)"
                )
                
                # Stocker la classification dans l'état
                state["results"]["error_classification"] = error_classification.model_dump()
                state["results"]["error_metrics"] = metrics
                
                # Logger le résumé de chaque groupe
                ordered_groups = get_priority_ordered_groups(error_classification)
                for i, group in enumerate(ordered_groups, 1):
                    logger.info(
                        f"  Groupe {i}: {group.category.value} "
                        f"(priorité: {group.priority}, "
                        f"fichiers: {len(group.files_involved)})"
                    )
                
                # Enrichir l'analyse d'erreur avec la classification
                error_analysis += f"\n\n## CLASSIFICATION DES ERREURS\n"
                error_analysis += f"Nombre de groupes d'erreurs: {metrics['total_groups']}\n"
                error_analysis += f"Réduction d'actions: {metrics['reduction_percentage']:.1f}%\n\n"
                
                for i, group in enumerate(ordered_groups, 1):
                    error_analysis += f"\n### Groupe {i}: {group.group_summary}\n"
                    error_analysis += f"- Catégorie: {group.category.value}\n"
                    error_analysis += f"- Priorité: {group.priority}\n"
                    error_analysis += f"- Cause: {group.probable_root_cause}\n"
                    error_analysis += f"- Stratégie: {group.fix_description}\n"
                    error_analysis += f"- Fichiers: {', '.join(group.files_involved)}\n"
                
            except Exception as e:
                logger.warning(f"⚠️ Échec classification LangChain: {e}")
                # Continuer sans classification
        
        # 2. Créer un prompt de debug pour Claude
        debug_prompt = await _create_debug_prompt(
            state["task"], latest_test_result, error_analysis, state
        )
        
        logger.info("🤖 Génération de correctifs avec Claude...")
    # Initialiser ai_messages si nécessaire
        
        # 3. Demander au LLM de proposer des corrections (avec fallback)
        debug_solution, provider_used = await _call_llm_with_fallback(
            anthropic_client, openai_client, debug_prompt, max_tokens=4000
        )
        
        logger.info(f"✅ Solution de debug générée avec {provider_used}")
        state["results"]["ai_messages"].append(f"🔧 Solution proposée:\n{debug_solution[:200]}...")
        
        # 4. Appliquer les corrections
        success = await _apply_debug_corrections(
            claude_tool, anthropic_client, openai_client, debug_solution, state
        )
        
        if success:
            state["results"]["ai_messages"].append("✅ Corrections appliquées avec succès")
            state["results"]["last_operation_result"] = f"Debug réussi (tentative {current_attempt})"
            logger.info(f"✅ Corrections appliquées - Tentative {current_attempt}")
    # Initialiser ai_messages si nécessaire
        else:
            state["results"]["ai_messages"].append("❌ Échec de l'application des corrections")
            state["results"]["last_operation_result"] = f"Debug échoué (tentative {current_attempt})"
            logger.error(f"❌ Échec des corrections - Tentative {current_attempt}")
        
        # 5. Retourner aux tests pour vérifier les corrections
        state["results"]["should_continue"] = True
        
    except Exception as e:
        error_msg = f"Exception lors du debug: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        state["results"]["error_logs"].append(error_msg)
        state["results"]["ai_messages"].append(f"❌ Exception debug: {error_msg}")
        state["results"]["last_operation_result"] = error_msg
        state["results"]["should_continue"] = True  # Continuer malgré l'exception
    
    logger.info(f"🏁 Debug terminé - Tentative {current_attempt}/3")
    # Initialiser ai_messages si nécessaire
    return state

async def _analyze_error_in_detail(test_result, state: Dict[str, Any], claude_tool: ClaudeCodeTool) -> str:
    """Analyse l'erreur en détail en examinant le code et les logs."""
    
    # Maintenant que tous les résultats sont des dictionnaires, utiliser .get() directement
    test_command = test_result.get("command", "N/A")
    exit_code = test_result.get("exit_code", -1)
    duration = test_result.get("duration", 0.0)
    stdout = test_result.get("output", "")
    stderr = test_result.get("error", "")
    
    analysis = f"""ANALYSE D'ERREUR DÉTAILLÉE

## Résultat du test
- Commande: {test_command}
- Code de sortie: {exit_code}
- Durée: {duration:.2f}s

## Sortie standard:
{stdout}

## Erreurs:
{stderr}

## Fichiers modifiés dans cette session:
{', '.join(state['results'].get('modified_files', []) or []) or 'Aucun'}

## Changements de code récents:
"""
    
    # Ajouter le contenu des fichiers modifiés récemment
    code_changes = state['results'].get("code_changes", {}) or {}
    for file_path, content in code_changes.items():
        analysis += f"\n### {file_path}:\n```\n{content[:500]}...\n```\n"
    
    # Essayer de lire des fichiers de log ou de configuration pertinents
    try:
        log_files = ["error.log", "debug.log", "test.log", ".pytest_cache/README.md"]
        for log_file in log_files:
            log_result = await claude_tool._arun(action="read_file", file_path=log_file)
            if log_result["success"]:
                analysis += f"\n### Contenu {log_file}:\n{log_result['content'][:300]}...\n"
    except Exception:
        pass
    
    return analysis

async def _create_debug_prompt(task, test_result, error_analysis: str, state: Dict[str, Any]) -> str:
    """Crée un prompt spécialisé pour le debug."""
    
    prompt = f"""Tu es un expert en debugging. Tu dois analyser et corriger les erreurs suivantes.

## TÂCHE ORIGINALE
**Titre**: {task.title}
**Description**: {task.description}

## TENTATIVE DE DEBUG
**Tentative actuelle**: {state['results'].get('debug_attempts', 1)}/3

## ANALYSE D'ERREUR
{error_analysis}

## HISTORIQUE DES ERREURS PRÉCÉDENTES
{chr(10).join(state['results'].get('error_logs', []) or []) or 'Aucune erreur précédente'}

## INSTRUCTIONS POUR LE DEBUG

1. **Identifie** la cause racine de l'erreur
2. **Propose** des corrections spécifiques
3. **Applique** les corrections de manière ciblée
4. **Évite** de refaire complètement le code sauf si nécessaire

Utilise ce format pour tes corrections:

```action:debug_fix
problem: [Description du problème identifié]
solution: [Description de la solution]
file_path: [Chemin du fichier à corriger]
content:
[Le contenu corrigé du fichier]
```

OU pour des commandes de correction:

```action:debug_command
problem: [Description du problème]
command: [Commande à exécuter]
explanation: [Pourquoi cette commande résout le problème]
```

**Concentre-toi sur UNE correction à la fois** pour éviter d'introduire de nouveaux bugs."""

    return prompt

async def _apply_debug_corrections(
    claude_tool: ClaudeCodeTool,
    anthropic_client: Client,
    openai_client: AsyncOpenAI,
    debug_solution: str,
    state: Dict[str, Any]
) -> bool:
    """Applique les corrections de debug proposées par Claude."""
    
    import re
    
    corrections_applied = 0
    total_corrections = 0
    
    # 1. Parser les corrections de fichiers
    fix_pattern = r'```action:debug_fix\n(.*?)\n```'
    fixes = re.findall(fix_pattern, debug_solution, re.DOTALL)
    
    for fix_content in fixes:
        total_corrections += 1
        logger.info(f"🔧 Application correction fichier {total_corrections}")
    # Initialiser ai_messages si nécessaire
        
        try:
            success = await _apply_file_fix(claude_tool, fix_content, state)
            if success:
                corrections_applied += 1
        except Exception as e:
            logger.error(f"Erreur lors de la correction fichier: {e}")
            state["results"]["error_logs"].append(f"Erreur correction fichier: {str(e)}")
    
    # 2. Parser les commandes de debug
    command_pattern = r'```action:debug_command\n(.*?)\n```'
    commands = re.findall(command_pattern, debug_solution, re.DOTALL)
    
    for command_content in commands:
        total_corrections += 1
        logger.info(f"🔧 Exécution commande debug {total_corrections}")
    # Initialiser ai_messages si nécessaire
        
        try:
            success = await _apply_debug_command(claude_tool, command_content, state)
            if success:
                corrections_applied += 1
        except Exception as e:
            logger.error(f"Erreur lors de la commande debug: {e}")
            state["results"]["error_logs"].append(f"Erreur commande debug: {str(e)}")
    
    # 3. Si aucune correction structurée, essayer d'appliquer directement
    if total_corrections == 0:
        logger.info("Aucune correction structurée trouvée, tentative d'application directe...")
    # Initialiser ai_messages si nécessaire
        success = await _apply_direct_debug_solution(claude_tool, debug_solution, state)
        if success:
            corrections_applied = 1
            total_corrections = 1
    
    success_rate = corrections_applied / max(total_corrections, 1)
    logger.info(f"📊 Corrections appliquées: {corrections_applied}/{total_corrections} (taux: {success_rate:.1%})")
    # Initialiser ai_messages si nécessaire
    
    return success_rate > 0  # Au moins une correction appliquée

async def _apply_file_fix(claude_tool: ClaudeCodeTool, fix_content: str, state: Dict[str, Any]) -> bool:
    """Applique une correction de fichier."""
    try:
        lines = fix_content.strip().split('\n')
        problem = ""
        solution = ""
        file_path = ""
        content = ""
        
        content_started = False
        for line in lines:
            if line.startswith('problem:'):
                problem = line.split(':', 1)[1].strip()
            elif line.startswith('solution:'):
                solution = line.split(':', 1)[1].strip()
            elif line.startswith('file_path:'):
                file_path = line.split(':', 1)[1].strip()
            elif line.startswith('content:'):
                content_started = True
            elif content_started:
                content += line + '\n'
        
        if file_path and content:
            # Sauvegarder l'ancien contenu pour rollback si nécessaire
            old_content_result = await claude_tool._arun(action="read_file", file_path=file_path)
            
            result = await claude_tool._arun(
                action="write_file",
                file_path=file_path,
                content=content.strip()
            )
            
            if result["success"]:
                state["results"]["code_changes"][file_path] = content.strip()
                if file_path not in state["results"]["modified_files"]:
                    state["results"]["modified_files"].append(file_path)
                
                state["results"]["ai_messages"].append(f"🔧 Correction appliquée: {file_path} - {problem}")
                logger.info(f"✅ Correction appliquée: {file_path}")
    # Initialiser ai_messages si nécessaire
                return True
            else:
                error = result.get("error", "Erreur inconnue")
                state["results"]["error_logs"].append(f"Échec correction {file_path}: {error}")
                logger.error(f"❌ Échec correction {file_path}: {error}")
                return False
        
        return False
        
    except Exception as e:
        logger.error(f"Erreur application correction fichier: {e}")
        return False

async def _apply_debug_command(claude_tool: ClaudeCodeTool, command_content: str, state: Dict[str, Any]) -> bool:
    """Applique une commande de debug."""
    try:
        lines = command_content.strip().split('\n')
        problem = ""
        command = ""
        explanation = ""
        
        for line in lines:
            if line.startswith('problem:'):
                problem = line.split(':', 1)[1].strip()
            elif line.startswith('command:'):
                command = line.split(':', 1)[1].strip()
            elif line.startswith('explanation:'):
                explanation = line.split(':', 1)[1].strip()
        
        if command:
            result = await claude_tool._arun(action="execute_command", command=command)
            
            if result["success"]:
                state["results"]["ai_messages"].append(f"🔧 Commande debug exécutée: {command}")
                logger.info(f"✅ Commande debug réussie: {command}")
    # Initialiser ai_messages si nécessaire
                return True
            else:
                error = result.get("stderr", result.get("error", "Erreur inconnue"))
                state["results"]["error_logs"].append(f"Échec commande debug '{command}': {error}")
                logger.error(f"❌ Échec commande debug '{command}': {error}")
                return False
        
        return False
        
    except Exception as e:
        logger.error(f"Erreur application commande debug: {e}")
        return False

async def _apply_direct_debug_solution(claude_tool: ClaudeCodeTool, debug_solution: str, state: Dict[str, Any]) -> bool:
    """Applique une solution de debug directe sans structure spécifique."""
    try:
        # Essayer d'extraire des blocs de code potentiels
        import re
        code_blocks = re.findall(r'```(?:python|javascript|typescript)?\n(.*?)\n```', debug_solution, re.DOTALL)
        
        if code_blocks:
            # Appliquer le premier bloc de code trouvé
            code_content = code_blocks[0]
            
            # Essayer de deviner le fichier basé sur les fichiers modifiés récemment
            target_file = None
            modified_files = getattr(state["results"], "modified_files", []) or []
            if modified_files:
                target_file = modified_files[-1]  # Dernier fichier modifié
            else:
                # Fichier par défaut basé sur le contenu
                if "def " in code_content or "import " in code_content:
                    target_file = "debug_fix.py"
                elif "function " in code_content or "const " in code_content:
                    target_file = "debug_fix.js"
                else:
                    target_file = "debug_fix.txt"
            
            result = await claude_tool._arun(
                action="write_file",
                file_path=target_file,
                content=code_content
            )
            
            if result["success"]:
                state["results"]["code_changes"][target_file] = code_content
                if target_file not in state["results"]["modified_files"]:
                    state["results"]["modified_files"].append(target_file)
                state["results"]["ai_messages"].append(f"🔧 Correction directe appliquée: {target_file}")
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Erreur application solution directe: {e}")
        return False 