"""Nœud d'analyse des requirements - analyse les spécifications et génère un plan."""

from typing import Dict, Any
from models.state import GraphState
from tools.ai_engine_hub import ai_hub, AIRequest, TaskType
from utils.logger import get_logger
from utils.persistence_decorator import with_persistence

logger = get_logger(__name__)


@with_persistence("analyze_requirements")
async def analyze_requirements(state: GraphState) -> GraphState:
    """
    Nœud d'analyse des requirements : analyse la tâche et détermine la stratégie d'implémentation.
    
    Ce nœud :
    1. Parse la description de la tâche
    2. Identifie les composants techniques nécessaires
    3. Détermine la complexité et les risques
    4. Prépare le contexte pour l'implémentation
    
    Args:
        state: État actuel du graphe
        
    Returns:
        État mis à jour avec l'analyse des requirements
    """
    logger.info(f"🔍 Analyse des requirements pour: {state['task'].title}")
    
    # ✅ CORRECTION CRITIQUE: Assurer l'intégrité de l'état dès le début
    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)

    state["results"]["current_status"] = "analyzing"
    state["results"]["ai_messages"].append("Début de l'analyse des requirements...")
    
    # Marquer le nœud comme en cours
    state["current_node"] = "analyze_requirements"
    
    try:
        task = state["task"]
        
        # 1. Préparer le contexte d'analyse
        analysis_context = {
            "task_title": task.title,
            "description": task.description,
            "task_type": task.task_type,
            "priority": task.priority,
            "acceptance_criteria": task.acceptance_criteria,
            "technical_context": task.technical_context,
            "files_to_modify": task.files_to_modify,
            "estimated_complexity": task.estimated_complexity,
            "repository_url": task.repository_url
        }
        
        # 2. Créer le prompt d'analyse détaillé
        analysis_prompt = _create_analysis_prompt(analysis_context)
        
        logger.info("🤖 Génération du plan d'analyse avec AI Engine Hub...")
        
        # 3. Utiliser l'AI Engine Hub pour analyser
        # Enrichir le contexte avec les IDs pour le monitoring
        analysis_context["workflow_id"] = state.get("workflow_id", "unknown")
        analysis_context["task_id"] = task.task_id
        
        ai_request = AIRequest(
            prompt=analysis_prompt,
            task_type=TaskType.ANALYSIS,
            context=analysis_context
        )
        
        response = await ai_hub.analyze_requirements(ai_request)
        
        if not response.success:
            error_msg = f"Erreur lors de l'analyse des requirements: {response.error}"
            logger.error(error_msg)
            state["error"] = error_msg
            return state
        
        # 4. Parser et structurer la réponse d'analyse
        analysis_result = _parse_analysis_response(response.content)
        
        # 5. Enrichir l'état avec les résultats d'analyse
        if not state["results"]:
            state["results"] = {}
            
        state["results"]["requirements_analysis"] = analysis_result
        
        # 6. Mettre à jour les informations de la tâche si nécessaire
        if analysis_result.get("refined_files_to_modify"):
            task.files_to_modify = analysis_result["refined_files_to_modify"]
        
        if analysis_result.get("refined_complexity"):
            task.estimated_complexity = analysis_result["refined_complexity"]
        
        # 7. Logs de résumé
        implementation_plan = analysis_result.get("implementation_plan", {})
        estimated_effort = analysis_result.get("estimated_effort", "Unknown")
        risk_level = analysis_result.get("risk_level", "Medium")
        
        logger.info("✅ Analyse requirements terminée",
                   estimated_effort=estimated_effort,
                   risk_level=risk_level,
                   files_count=len(analysis_result.get("refined_files_to_modify", [])),
                   steps_count=len(implementation_plan.get("steps", [])))
        
        # 8. Préparer les informations pour les nœuds suivants
        state["results"]["analysis_summary"] = {
            "complexity_score": analysis_result.get("complexity_score", 5),
            "estimated_duration_minutes": analysis_result.get("estimated_duration_minutes", 30),
            "requires_external_deps": analysis_result.get("requires_external_deps", False),
            "breaking_changes_risk": analysis_result.get("breaking_changes_risk", False),
            "test_strategy": analysis_result.get("test_strategy", "unit"),
            "implementation_approach": analysis_result.get("implementation_approach", "standard")
        }
        
        return state
        
    except Exception as e:
        error_msg = f"Exception lors de l'analyse des requirements: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["error"] = error_msg
        return state


def _create_analysis_prompt(context: Dict[str, Any]) -> str:
    """Crée un prompt détaillé pour l'analyse des requirements."""
    
    prompt = f"""
# 🔍 ANALYSE DÉTAILLÉE DES REQUIREMENTS - AI-Agent

Tu es un expert en analyse de requirements pour le développement logiciel automatisé.
Analyse en profondeur cette tâche et génère un plan d'implémentation structuré.

## 📋 INFORMATIONS DE LA TÂCHE

**Titre**: {context['task_title']}
**Type**: {context['task_type']}
**Priorité**: {context['priority']}

**Description**: 
{context['description']}

**Critères d'acceptation**:
{context.get('acceptance_criteria', 'Non spécifiés')}

**Contexte technique**:
{context.get('technical_context', 'Non spécifié')}

**Fichiers suggérés à modifier**:
{context.get('files_to_modify', 'Non spécifiés')}

**Complexité estimée initiale**: {context.get('estimated_complexity', 'Non évaluée')}

**Repository**: {context['repository_url']}

## 🎯 TÂCHES D'ANALYSE REQUISES

Fournis une analyse structurée au format JSON avec les clés suivantes :

```json
{{
    "summary": "Résumé en 2-3 phrases de ce qui doit être fait",
    "complexity_analysis": {{
        "complexity_score": "Nombre de 1 à 10",
        "complexity_factors": ["Liste des facteurs de complexité"],
        "technical_challenges": ["Défis techniques identifiés"]
    }},
    "implementation_plan": {{
        "approach": "Approche d'implémentation recommandée",
        "steps": [
            {{
                "step": 1,
                "description": "Description de l'étape",
                "estimated_time_minutes": 15,
                "dependencies": ["Dépendances de cette étape"],
                "deliverables": ["Livrables de cette étape"]
            }}
        ]
    }},
    "files_analysis": {{
        "refined_files_to_modify": ["Liste affinée des fichiers à modifier"],
        "new_files_to_create": ["Nouveaux fichiers à créer"],
        "files_to_test": ["Fichiers nécessitant des tests spécifiques"]
    }},
    "requirements_breakdown": {{
        "functional_requirements": ["Requirements fonctionnels"],
        "non_functional_requirements": ["Requirements non-fonctionnels"],
        "acceptance_criteria_refined": ["Critères d'acceptation détaillés"]
    }},
    "risk_assessment": {{
        "risk_level": "Low/Medium/High",
        "potential_risks": ["Risques identifiés"],
        "mitigation_strategies": ["Stratégies d'atténuation"]
    }},
    "testing_strategy": {{
        "test_types_needed": ["unit", "integration", "e2e"],
        "test_scenarios": ["Scénarios de test clés"],
        "edge_cases": ["Cas limites à tester"]
    }},
    "external_dependencies": {{
        "requires_external_deps": false,
        "new_packages_needed": ["Nouveaux packages requis"],
        "api_integrations": ["Intégrations API nécessaires"]
    }},
    "estimated_effort": {{
        "estimated_duration_minutes": 45,
        "confidence_level": "High/Medium/Low",
        "effort_breakdown": {{
            "analysis": 10,
            "implementation": 25,
            "testing": 10,
            "debugging": 5,
            "documentation": 5
        }}
    }},
    "success_criteria": {{
        "definition_of_done": ["Critères de fin de tâche"],
        "quality_gates": ["Seuils de qualité à respecter"],
        "acceptance_tests": ["Tests d'acceptation à valider"]
    }}
}}
```

## 🚨 INSTRUCTIONS IMPORTANTES

1. **Sois spécifique** : Évite les généralités, donne des détails concrets
2. **Pense aux dépendances** : Identifie les interconnexions entre composants
3. **Considère la maintenance** : L'impact sur le code existant
4. **Anticipe les problèmes** : Les points de friction potentiels
5. **Optimise pour l'automatisation** : Plan adapté à l'exécution par AI-Agent

Réponds UNIQUEMENT avec le JSON structuré, sans texte additionnel.
"""
    
    return prompt


def _parse_analysis_response(response_content: str) -> Dict[str, Any]:
    """Parse et valide la réponse d'analyse IA avec gestion intelligente code/JSON."""
    
    import json
    import re
    
    try:
        logger.info(f"🔍 Parsing réponse IA: {response_content[:200]}...")
        
        # Étape 1: Détecter si c'est du code ou du JSON
        if _is_code_response(response_content):
            logger.info("🔍 Détection: Réponse contient du code - Extraction intelligente")
            return _extract_analysis_from_code_response(response_content)
        
        # Étape 2: Rechercher JSON dans différents formats de blocs
        json_str = None
        
        # Rechercher blocs JSON markdown
        json_patterns = [
            r'```json\s*(\{.*?\})\s*```',  # ```json { ... } ```
            r'```javascript\s*(\{.*?\})\s*```',  # ```javascript { ... } ```
            r'```js\s*(\{.*?\})\s*```',  # ```js { ... } ```
            r'```\s*(\{.*?\})\s*```',  # ``` { ... } ```
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, response_content, re.DOTALL)
            if match:
                json_str = match.group(1)
                logger.info(f"✅ JSON trouvé avec pattern: {pattern[:20]}...")
                break
        
        # Fallback : rechercher directement un objet JSON
        if not json_str:
            json_match = re.search(r'\{[^}]*(?:\{[^}]*\}[^}]*)*\}', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                logger.info("✅ JSON trouvé par regex directe")
            else:
                logger.warning("⚠️ Aucun JSON détecté - Génération analyse par défaut")
                return _generate_analysis_from_text(response_content)
        
        # Étape 2: Nettoyer et convertir JavaScript en JSON valide
        json_str = json_str.strip()
        logger.info(f"🧹 Nettoyage JSON: {json_str[:100]}...")
        
        # Supprimer les commentaires JavaScript
        json_str = re.sub(r'//.*?\n', '\n', json_str)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        
        # Convertir guillemets simples en doubles (clés et valeurs)
        json_str = re.sub(r"'([^']*)'(\s*:)", r'"\1"\2', json_str)  # Clés
        json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)   # Valeurs
        
        # Nettoyer les virgules trainantes
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # Nettoyer les retours à la ligne dans les strings
        json_str = re.sub(r'\n\s*', ' ', json_str)
        
        # Corriger les propriétés JavaScript sans guillemets
        json_str = re.sub(r'(\w+)(\s*:)', r'"\1"\2', json_str)
        
        logger.info(f"✅ JSON nettoyé: {json_str[:100]}...")
        
        # Étape 3: Parser le JSON
        try:
            analysis_result = json.loads(json_str)
            logger.info("✅ JSON parsé avec succès")
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Erreur JSON parsing: {e}")
            logger.info("🔧 Tentative réparation du JSON...")
            # Tentative de réparation automatique du JSON
            try:
                json_str = _repair_json(json_str)
                analysis_result = json.loads(json_str)
                logger.info("✅ JSON réparé et parsé avec succès")
            except Exception as repair_error:
                logger.error(f"❌ Impossible de réparer le JSON: {repair_error}")
                logger.error(f"JSON problématique: {json_str[:500]}...")
                return _get_default_analysis_with_error(f"JSON invalide: {str(e)}")
        
        # Validation et valeurs par défaut
        default_analysis = {
            "summary": "Analyse en cours...",
            "complexity_score": 5,
            "estimated_duration_minutes": 30,
            "risk_level": "Medium",
            "refined_files_to_modify": [],
            "implementation_plan": {"steps": []},
            "requires_external_deps": False,
            "breaking_changes_risk": False,
            "test_strategy": "unit",
            "implementation_approach": "standard"
        }
        
        # Fusionner avec les valeurs par défaut
        for key, default_value in default_analysis.items():
            if key not in analysis_result:
                analysis_result[key] = default_value
        
        # Extraire les valeurs importantes vers le niveau racine
        if "complexity_analysis" in analysis_result:
            analysis_result["complexity_score"] = analysis_result["complexity_analysis"].get("complexity_score", 5)
        
        if "estimated_effort" in analysis_result:
            analysis_result["estimated_duration_minutes"] = analysis_result["estimated_effort"].get("estimated_duration_minutes", 30)
        
        if "risk_assessment" in analysis_result:
            analysis_result["risk_level"] = analysis_result["risk_assessment"].get("risk_level", "Medium")
        
        if "files_analysis" in analysis_result:
            analysis_result["refined_files_to_modify"] = analysis_result["files_analysis"].get("refined_files_to_modify", [])
        
        if "external_dependencies" in analysis_result:
            analysis_result["requires_external_deps"] = analysis_result["external_dependencies"].get("requires_external_deps", False)
        
        return analysis_result
        
    except json.JSONDecodeError as e:
        logger.error(f"Erreur parsing JSON analyse: {e}")
        if 'json_str' in locals():
            logger.error(f"JSON problématique (premiers 500 chars): {json_str[:500]}")
            logger.error(f"Erreur à la position {e.pos}: caractère '{json_str[e.pos:e.pos+10] if e.pos < len(json_str) else 'fin'}'")
            
            # Tentative de réparation avancée
            try:
                repaired_json = _advanced_json_repair(json_str)
                logger.info("Tentative de réparation JSON avancée...")
                analysis_result = json.loads(repaired_json)
                logger.info("✅ Réparation JSON réussie!")
                
                # Fusionner avec les valeurs par défaut après réparation
                default_analysis = {
                    "summary": "Analyse en cours...",
                    "complexity_score": 5,
                    "estimated_duration_minutes": 30,
                    "risk_level": "Medium",
                    "refined_files_to_modify": [],
                    "implementation_plan": {"steps": []},
                    "requires_external_deps": False,
                    "breaking_changes_risk": False,
                    "test_strategy": "unit",
                    "implementation_approach": "standard"
                }
                
                for key, default_value in default_analysis.items():
                    if key not in analysis_result:
                        analysis_result[key] = default_value
                        
                return analysis_result
                
            except Exception as repair_error:
                logger.error(f"Échec réparation JSON avancée: {repair_error}")
        else:
            logger.error("Variable json_str non disponible pour debug")
            
        return _get_default_analysis_with_error(f"Erreur parsing JSON: {str(e)}", response_content)
        
    except Exception as e:
        logger.error(f"Erreur inattendue parsing analyse: {e}")
        return _get_default_analysis_with_error(f"Erreur inattendue: {str(e)}", response_content, "High")


def _repair_json(json_str: str) -> str:
    """Tentative de réparation automatique d'un JSON malformé."""
    import re
    
    # Supprimer les commentaires JavaScript
    json_str = re.sub(r'//.*?\n', '', json_str)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    
    # Corriger les virgules en trop
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    
    # Ajouter des guillemets manquants aux clés (seulement si pas déjà présents)
    json_str = re.sub(r'(?<!")(\w+)(?!"):', r'"\1":', json_str)
    
    # Remplacer les guillemets simples par des doubles dans les valeurs
    json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)
    
    # Corriger les valeurs booléennes
    json_str = re.sub(r':\s*true\b', ': true', json_str)
    json_str = re.sub(r':\s*false\b', ': false', json_str)
    json_str = re.sub(r':\s*null\b', ': null', json_str)
    
    return json_str


def _advanced_json_repair(json_str: str) -> str:
    """Réparation JSON avancée avec détection d'erreurs spécifiques."""
    import re
    logger.info("🔧 Début réparation JSON avancée...")
    
    # 1. Supprimer les balises markdown JSON si présentes
    json_str = re.sub(r'^```json\s*', '', json_str)
    json_str = re.sub(r'\s*```$', '', json_str)
    
    # 2. Nettoyer les caractères invisibles et de contrôle
    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
    
    # 3. Corriger les clés sans guillemets (SIMPLE et efficace)
    json_str = re.sub(r'(\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', json_str)
    
    # 4. Corriger les guillemets simples en doubles pour les valeurs (SIMPLE)
    json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)
    
    # 5. Supprimer les virgules en trop avant les accolades/crochets fermants
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
    
    # 6. Corriger les valeurs booléennes Python en JSON
    json_str = re.sub(r':\s*True\b', ': true', json_str)
    json_str = re.sub(r':\s*False\b', ': false', json_str)
    json_str = re.sub(r':\s*None\b', ': null', json_str)
    
    # 7. Supprimer les commentaires JavaScript/Python
    json_str = re.sub(r'//.*?\n', '\n', json_str)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    json_str = re.sub(r'#.*?\n', '\n', json_str)
    
    # 8. Normaliser les espaces multiples
    json_str = re.sub(r'\s+', ' ', json_str)
    json_str = json_str.strip()
    
    logger.info(f"🔧 JSON après réparation (premiers 200 chars): {json_str[:200]}")
    
    return json_str


def _is_code_response(response: str) -> bool:
    """Détecte si la réponse contient principalement du code plutôt que du JSON."""
    code_indicators = [
        'def ', 'function ', 'class ', 'import ', 'from ',
        'const ', 'let ', 'var ', 'if __name__',
        '```python', '```javascript', '```js', '```typescript'
    ]
    
    json_indicators = [
        '"summary":', '"complexity_score":', '"implementation_plan":',
        '"estimated_duration":', '"risk_level":'
    ]
    
    code_score = sum(1 for indicator in code_indicators if indicator in response)
    json_score = sum(1 for indicator in json_indicators if indicator in response)
    
    return code_score > json_score


def _extract_analysis_from_code_response(response: str) -> Dict[str, Any]:
    """Extrait une analyse intelligente d'une réponse contenant du code."""
    import re
    
    logger.info("🧠 Analyse intelligente de la réponse code")
    
    # Analyser la complexité basée sur le code généré
    complexity_score = _estimate_complexity_from_code(response)
    
    # Extraire les fichiers mentionnés
    files_mentioned = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*\.(py|js|ts|jsx|tsx|html|css))', response)
    refined_files = list(set([f[0] for f in files_mentioned]))
    
    # Détecter les dépendances externes
    has_imports = bool(re.search(r'(import|require|from)\s+[\'"][^\'"]+[\'"]', response))
    
    # Estimer la durée basée sur la quantité de code
    lines_count = len([line for line in response.split('\n') if line.strip() and not line.strip().startswith('#')])
    estimated_duration = max(30, min(180, lines_count * 2))
    
    return {
        "summary": f"Analyse basée sur le code généré ({lines_count} lignes de code détectées)",
        "complexity_score": complexity_score,
        "estimated_duration_minutes": estimated_duration,
        "risk_level": "Low" if complexity_score <= 3 else "Medium" if complexity_score <= 7 else "High",
        "refined_files_to_modify": refined_files,
        "implementation_plan": {
            "steps": [
                "Créer les fichiers de base identifiés",
                "Implémenter la logique principale",
                "Ajouter la gestion d'erreurs",
                "Écrire les tests correspondants"
            ]
        },
        "requires_external_deps": has_imports,
        "breaking_changes_risk": False,
        "test_strategy": "unit",
        "implementation_approach": "code-first",
        "code_analysis": {
            "lines_detected": lines_count,
            "files_mentioned": refined_files,
            "has_external_deps": has_imports,
            "generated_from_code": True
        }
    }


def _estimate_complexity_from_code(code: str) -> int:
    """Estime la complexité basée sur le code généré."""
    complexity_indicators = {
        'class ': 2, 'def ': 1, 'if ': 1, 'for ': 1, 'while ': 1,
        'try:': 2, 'except': 2, 'async ': 2, 'await ': 1,
        'import ': 0.5, 'from ': 0.5
    }
    
    score = 0
    for indicator, weight in complexity_indicators.items():
        count = code.count(indicator)
        score += count * weight
    
    return min(10, max(1, int(score / 3)))  # Normaliser entre 1-10


def _generate_analysis_from_text(response: str) -> Dict[str, Any]:
    """Génère une analyse basée sur le texte de réponse."""
    
    # Analyser le contenu textuel pour extraire des informations
    word_count = len(response.split())
    
    # Détecter la complexité basée sur des mots-clés
    complexity_keywords = ['complex', 'difficult', 'challenge', 'multiple', 'integration', 'advanced']
    simple_keywords = ['simple', 'basic', 'easy', 'straightforward', 'quick']
    
    complexity_mentions = sum(1 for keyword in complexity_keywords if keyword.lower() in response.lower())
    simple_mentions = sum(1 for keyword in simple_keywords if keyword.lower() in response.lower())
    
    if simple_mentions > complexity_mentions:
        complexity_score = 3
        estimated_duration = 30
        risk_level = "Low"
    elif complexity_mentions > simple_mentions:
        complexity_score = 7
        estimated_duration = 90
        risk_level = "Medium"
    else:
        complexity_score = 5
        estimated_duration = 60
        risk_level = "Medium"
    
    return {
        "summary": f"Analyse textuelle de la réponse IA ({word_count} mots)",
        "complexity_score": complexity_score,
        "estimated_duration_minutes": estimated_duration,
        "risk_level": risk_level,
        "refined_files_to_modify": [],
        "implementation_plan": {
            "steps": [
                "Analyser les exigences détaillées",
                "Concevoir l'architecture",
                "Implémenter étape par étape",
                "Tester et valider"
            ]
        },
        "requires_external_deps": 'install' in response.lower() or 'dependency' in response.lower(),
        "breaking_changes_risk": 'breaking' in response.lower() or 'incompatible' in response.lower(),
        "test_strategy": "unit",
        "implementation_approach": "text-analysis",
        "text_analysis": {
            "word_count": word_count,
            "complexity_indicators": complexity_mentions,
            "simplicity_indicators": simple_mentions,
            "generated_from_text": True
        }
    }


def _get_default_analysis_with_error(error_msg: str, raw_response: str = "", risk_level: str = "Medium") -> Dict[str, Any]:
    """Retourne une analyse par défaut en cas d'erreur de parsing."""
    return {
        "error": error_msg,
        "raw_response": raw_response[:500] if raw_response else "",  # Premiers 500 caractères pour debug
        "summary": "Analyse non disponible en raison d'une erreur de parsing",
        "complexity_score": 5,
        "estimated_duration_minutes": 30,
        "risk_level": risk_level,
        "refined_files_to_modify": [],
        "implementation_plan": {"steps": []},
        "requires_external_deps": False,
        "breaking_changes_risk": False,
        "test_strategy": "unit",
        "implementation_approach": "standard"
    } 