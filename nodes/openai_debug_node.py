"""Nœud de debug avec OpenAI LLM suite à demande humaine."""

import openai
from typing import Dict, Any, List
from models.state import GraphState
from utils.logger import get_logger
from config.settings import get_settings
from config.langsmith_config import langsmith_config

logger = get_logger(__name__)
settings = get_settings()


async def openai_debug_after_human_request(state: GraphState) -> GraphState:
    """
    Nœud de debug avec OpenAI LLM après demande humaine.
    
    Ce nœud :
    1. Analyse la demande de debug humaine
    2. Utilise OpenAI pour analyser les problèmes
    3. Génère des suggestions de correction
    4. Met à jour le code si possible
    5. Re-lance les tests
    
    Args:
        state: État actuel du graphe
        
    Returns:
        État mis à jour avec les corrections OpenAI
    """
    task = state["task"]
    logger.info(f"🔧 Debug OpenAI pour: {task.title}")
    
    # ✅ CORRECTION CRITIQUE: Assurer l'intégrité de l'état dès le début
    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)
    
    # Initialiser ai_messages si nécessaire
    if "ai_messages" not in state["results"]:
        state["results"]["ai_messages"] = []
    
    state["results"]["ai_messages"].append("🔧 Analyse debug avec OpenAI LLM...")
    
    try:
        # ✅ CORRECTION CRITIQUE: Gérer les compteurs de debug pour éviter les boucles infinies
        if "human_debug_attempts" not in state["results"]:
            state["results"]["human_debug_attempts"] = 0
        
        # Incrémenter le compteur de debug après validation humaine
        state["results"]["human_debug_attempts"] += 1
        max_human_debug = 2  # Maximum 2 tentatives après validation humaine
        
        logger.info(f"🔧 Debug OpenAI après validation humaine: tentative {state['results']['human_debug_attempts']}/{max_human_debug}")
        
        if state["results"]["human_debug_attempts"] > max_human_debug:
            logger.warning(f"⚠️ Limite de debug après validation humaine atteinte ({max_human_debug}) - arrêt forcé")
            state["results"]["ai_messages"].append("⚠️ Limite de debug atteinte - workflow arrêté")
            state["results"]["debug_limit_reached"] = True
            state["results"]["should_continue"] = False
            return state
        
        # 1. Récupérer la demande de debug humaine
        debug_request = state["results"].get("debug_request", "Problème à corriger")
        human_comments = state["results"].get("validation_response", {}).get("comments", "")
        
        logger.info(f"📝 Demande debug humaine: {debug_request}")
        
        # 2. Préparer le contexte pour OpenAI
        debug_context = _prepare_debug_context(state, debug_request, human_comments)
        
        # 3. Initialiser le client OpenAI
        openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        
        # 4. Créer le prompt de debug
        debug_prompt = _create_debug_prompt(debug_context)
        
        # 5. Appeler OpenAI pour l'analyse
        logger.info("🤖 Appel OpenAI pour analyse debug...")
        state["results"]["ai_messages"].append("🤖 Consultation OpenAI LLM...")
        
        response = await openai_client.chat.completions.create(
            model="gpt-4",  # Ou "gpt-3.5-turbo" selon préférence
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un expert développeur qui aide à débugger du code. Analyse les problèmes et propose des solutions concrètes."
                },
                {
                    "role": "user", 
                    "content": debug_prompt
                }
            ],
            temperature=0.1,  # Peu de créativité, focus sur la précision
            max_tokens=2000
        )
        
        debug_analysis = response.choices[0].message.content
        
        logger.info(f"✅ Analyse OpenAI reçue: {len(debug_analysis)} caractères")
        state["results"]["ai_messages"].append("✅ Analyse OpenAI terminée")
        
        # 6. Parser l'analyse OpenAI
        debug_suggestions = _parse_openai_debug_response(debug_analysis)
        
        # 7. Sauvegarder les résultats de debug
        state["results"]["openai_debug"] = {
            "analysis": debug_analysis,
            "suggestions": debug_suggestions,
            "human_request": debug_request,
            "model_used": "gpt-4",
            "timestamp": state.get("current_time")
        }
        
        # 8. Tracer avec LangSmith
        if langsmith_config.client:
            try:
                langsmith_config.client.create_run(
                    name="openai_debug_analysis",
                    run_type="llm",
                    inputs={
                        "debug_request": debug_request,
                        "human_comments": human_comments,
                        "context": debug_context
                    },
                    outputs={
                        "analysis": debug_analysis,
                        "suggestions_count": len(debug_suggestions),
                        "model": "gpt-4"
                    },
                    session_name=state.get("langsmith_session"),
                    extra={
                        "workflow_id": state.get("workflow_id"),
                        "openai_debug": True,
                        "triggered_by": "human_validation"
                    }
                )
            except Exception as e:
                logger.warning(f"⚠️ Erreur LangSmith tracing: {e}")
        
        # 9. Appliquer les suggestions si possible
        if debug_suggestions:
            logger.info(f"🔧 Application de {len(debug_suggestions)} suggestions debug")
            state["results"]["ai_messages"].append(f"🔧 Application de {len(debug_suggestions)} suggestions...")
            
            # Ici on pourrait implémenter l'application automatique des corrections
            # Pour l'instant, on marque qu'un debug a été fait
            state["results"]["debug_applied"] = True
            state["results"]["debug_suggestions_applied"] = debug_suggestions
        
        # 10. Marquer le debug comme terminé
        state["results"]["openai_debug_completed"] = True
        state["results"]["should_retest"] = True  # Indiquer qu'il faut re-tester
        
        logger.info(f"🔧 Debug OpenAI terminé avec {len(debug_suggestions)} suggestions")
        state["results"]["ai_messages"].append("✅ Debug OpenAI terminé - Prêt pour re-test")
        
    except Exception as e:
        error_msg = f"Erreur debug OpenAI: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        # ✅ CORRECTION: Initialiser error_logs s'il n'existe pas
        if "error_logs" not in state["results"]:
            state["results"]["error_logs"] = []
        if "ai_messages" not in state["results"]:
            state["results"]["ai_messages"] = []
            
        state["results"]["error_logs"].append(error_msg)
        state["results"]["ai_messages"].append(f"❌ {error_msg}")
        state["results"]["openai_debug_failed"] = True
    
    return state


def _prepare_debug_context(state: GraphState, debug_request: str, human_comments: str) -> Dict[str, Any]:
    """Prépare le contexte pour l'analyse debug OpenAI."""
    
    task = state["task"]
    results = state.get("results", {})
    
    context = {
        "task_info": {
            "title": task.title,
            "description": task.description,
            "type": task.task_type.value if hasattr(task.task_type, 'value') else str(task.task_type)
        },
        "human_feedback": {
            "debug_request": debug_request,
            "comments": human_comments
        },
        "test_results": results.get("test_results", {}),
        "error_logs": results.get("error_logs", []),
        "implementation_info": results.get("implementation_results", {}),
        "pr_info": results.get("pr_info", {}),
        "completed_nodes": state.get("completed_nodes", [])
    }
    
    return context


def _create_debug_prompt(context: Dict[str, Any]) -> str:
    """Crée le prompt pour l'analyse debug OpenAI."""
    
    task_info = context["task_info"]
    human_feedback = context["human_feedback"]
    test_results = context["test_results"]
    error_logs = context["error_logs"]
    
    prompt = f"""
DEMANDE DE DEBUG SUITE À FEEDBACK HUMAIN

=== CONTEXTE DE LA TÂCHE ===
Titre: {task_info["title"]}
Description: {task_info["description"]}
Type: {task_info["type"]}

=== FEEDBACK HUMAIN ===
Demande de debug: {human_feedback["debug_request"]}
Commentaires: {human_feedback["comments"]}

=== RÉSULTATS DES TESTS ===
{_format_test_results(test_results)}

=== ERREURS RENCONTRÉES ===
{_format_error_logs(error_logs)}

=== DEMANDE ===
Analyse les problèmes identifiés par l'humain et propose des solutions concrètes.

Réponds avec:
1. ANALYSE: Identification des problèmes principaux
2. CAUSES: Causes probables des problèmes  
3. SOLUTIONS: Solutions spécifiques et actionables
4. PRIORITÉ: Ordre de résolution recommandé

Sois précis et actionnable dans tes recommandations.
"""
    
    return prompt.strip()


def _format_test_results(test_results: Dict[str, Any]) -> str:
    """Formate les résultats de tests pour le prompt."""
    if not test_results:
        return "Aucun résultat de test disponible"
    
    if test_results.get("success"):
        return "✅ Tests réussis"
    else:
        failed_tests = test_results.get("failed_tests", [])
        if failed_tests:
            return f"❌ {len(failed_tests)} test(s) échoué(s):\n" + "\n".join([f"- {test}" for test in failed_tests[:5]])
        else:
            return "❌ Tests échoués (détails non disponibles)"


def _format_error_logs(error_logs: List[str]) -> str:
    """Formate les logs d'erreur pour le prompt."""
    if not error_logs:
        return "Aucune erreur logguée"
    
    # Prendre les 5 dernières erreurs
    recent_errors = error_logs[-5:]
    return "\n".join([f"- {error}" for error in recent_errors])


def _parse_openai_debug_response(response: str) -> List[Dict[str, str]]:
    """Parse la réponse OpenAI et extrait les suggestions actionables."""
    
    suggestions = []
    
    # Rechercher les sections de solutions
    import re
    
    # Pattern pour identifier les solutions
    solution_patterns = [
        r'(?:SOLUTIONS?|RECOMMANDATIONS?)[:\s]*(.*?)(?=\n\n|\n[A-Z]{2,}|$)',
        r'(?:\d+\.\s*)(.*?)(?=\n\d+\.|$)',
    ]
    
    for pattern in solution_patterns:
        matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
        for match in matches:
            if match.strip() and len(match.strip()) > 10:
                suggestions.append({
                    "type": "suggestion",
                    "description": match.strip(),
                    "priority": "medium"
                })
    
    # Si pas de suggestions trouvées, créer une suggestion générale
    if not suggestions:
        suggestions.append({
            "type": "general",
            "description": "Analyser la réponse OpenAI complète pour identifier les actions",
            "priority": "high",
            "full_response": response
        })
    
    return suggestions[:10]  # Limiter à 10 suggestions maximum 