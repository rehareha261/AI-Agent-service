"""Chaîne LangChain pour la génération de plans d'implémentation structurés."""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class RiskLevel(str, Enum):
    """Niveau de risque pour une étape d'implémentation."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ImplementationStep(BaseModel):
    """Modèle Pydantic pour une étape d'implémentation."""
    step_number: int = Field(description="Numéro de l'étape (séquentiel)")
    title: str = Field(description="Titre court de l'étape")
    description: str = Field(description="Description détaillée de ce qui doit être fait")
    files_to_modify: List[str] = Field(
        default_factory=list,
        description="Liste des fichiers à créer ou modifier"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Dépendances/packages requis pour cette étape"
    )
    estimated_complexity: int = Field(
        ge=1,
        le=10,
        description="Complexité estimée (1=très simple, 10=très complexe)"
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.LOW,
        description="Niveau de risque de cette étape"
    )
    risk_mitigation: Optional[str] = Field(
        default=None,
        description="Stratégie de mitigation du risque si risque > LOW"
    )
    validation_criteria: List[str] = Field(
        default_factory=list,
        description="Critères de validation pour considérer l'étape comme terminée"
    )


class ImplementationPlan(BaseModel):
    """Modèle Pydantic pour un plan d'implémentation complet."""
    task_summary: str = Field(description="Résumé de la tâche à implémenter")
    architecture_approach: str = Field(
        description="Approche architecturale recommandée"
    )
    steps: List[ImplementationStep] = Field(
        min_length=1,
        description="Liste ordonnée des étapes d'implémentation"
    )
    total_estimated_complexity: int = Field(
        ge=1,
        description="Complexité totale estimée (somme des complexités)"
    )
    overall_risk_assessment: str = Field(
        description="Évaluation globale des risques du projet"
    )
    recommended_testing_strategy: str = Field(
        description="Stratégie de tests recommandée"
    )
    potential_blockers: List[str] = Field(
        default_factory=list,
        description="Liste des bloqueurs potentiels identifiés"
    )
    
    class Config:
        """Configuration Pydantic."""
        json_schema_extra = {
            "example": {
                "task_summary": "Créer une API REST pour gérer les utilisateurs",
                "architecture_approach": "Architecture MVC avec FastAPI",
                "steps": [
                    {
                        "step_number": 1,
                        "title": "Créer les modèles de données",
                        "description": "Définir les modèles Pydantic pour User",
                        "files_to_modify": ["models/user.py"],
                        "dependencies": ["pydantic"],
                        "estimated_complexity": 3,
                        "risk_level": "low",
                        "validation_criteria": ["Modèles valident correctement"]
                    }
                ],
                "total_estimated_complexity": 15,
                "overall_risk_assessment": "Risque faible, technologies matures",
                "recommended_testing_strategy": "Tests unitaires + tests d'intégration",
                "potential_blockers": ["Schéma DB non finalisé"]
            }
        }


def create_implementation_plan_chain(
    provider: str = "anthropic",
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 4000
):
    """
    Crée une chaîne LCEL pour générer un plan d'implémentation structuré.
    
    Args:
        provider: Provider LLM à utiliser ("anthropic" ou "openai")
        model: Nom du modèle (optionnel, utilise le défaut du provider)
        temperature: Température du modèle (0.0-1.0)
        max_tokens: Nombre maximum de tokens
        
    Returns:
        Chaîne LCEL configurée (Prompt → LLM → Parser)
        
    Raises:
        ValueError: Si le provider n'est pas supporté
        Exception: Si les clés API sont manquantes
    """
    logger.info(f"🔗 Création implementation_plan_chain avec provider={provider}")
    
    # 1. Créer le parser Pydantic
    parser = PydanticOutputParser(pydantic_object=ImplementationPlan)
    
    # 2. Créer le prompt template avec instructions de formatage
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """Tu es un architecte logiciel expert qui crée des plans d'implémentation détaillés et structurés.
Tu dois analyser la tâche fournie et générer un plan complet au format JSON strict.

IMPORTANT: Tu DOIS retourner UNIQUEMENT du JSON valide, sans texte avant ou après.
Utilise le schéma suivant:

{format_instructions}

Sois précis, actionnable et identifie tous les risques potentiels."""),
        ("user", """Tâche à analyser:

Titre: {task_title}
Description: {task_description}
Type: {task_type}
Contexte additionnel: {additional_context}

Génère un plan d'implémentation complet et structuré.""")
    ])
    
    # 3. Injecter les instructions de formatage du parser dans le prompt
    prompt = prompt_template.partial(format_instructions=parser.get_format_instructions())
    
    # 4. Créer le LLM selon le provider
    if provider.lower() == "anthropic":
        if not settings.anthropic_api_key:
            raise Exception("ANTHROPIC_API_KEY manquante dans la configuration")
        
        llm = ChatAnthropic(
            model=model or "claude-3-5-sonnet-20241022",
            anthropic_api_key=settings.anthropic_api_key,
            temperature=temperature,
            max_tokens=max_tokens
        )
        logger.info(f"✅ LLM Anthropic initialisé: {model or 'claude-3-5-sonnet-20241022'}")
        
    elif provider.lower() == "openai":
        if not settings.openai_api_key:
            raise Exception("OPENAI_API_KEY manquante dans la configuration")
        
        llm = ChatOpenAI(
            model=model or "gpt-4",
            openai_api_key=settings.openai_api_key,
            temperature=temperature,
            max_tokens=max_tokens
        )
        logger.info(f"✅ LLM OpenAI initialisé: {model or 'gpt-4'}")
        
    else:
        raise ValueError(f"Provider non supporté: {provider}. Utilisez 'anthropic' ou 'openai'")
    
    # 5. Créer la chaîne LCEL: Prompt → LLM → Parser
    chain = prompt | llm | parser
    
    logger.info("✅ Implementation plan chain créée avec succès")
    return chain


async def generate_implementation_plan(
    task_title: str,
    task_description: str,
    task_type: str = "feature",
    additional_context: Optional[Dict[str, Any]] = None,
    provider: str = "anthropic",
    fallback_to_openai: bool = True,
    run_step_id: Optional[int] = None
) -> ImplementationPlan:
    """
    Génère un plan d'implémentation structuré avec fallback automatique.
    
    Args:
        task_title: Titre de la tâche
        task_description: Description détaillée
        task_type: Type de tâche (feature, bugfix, refactor, etc.)
        additional_context: Contexte additionnel (dict)
        provider: Provider principal ("anthropic" ou "openai")
        fallback_to_openai: Si True, fallback vers OpenAI si le provider principal échoue
        
    Returns:
        ImplementationPlan validé par Pydantic
        
    Raises:
        Exception: Si tous les providers échouent
    """
    context_str = str(additional_context) if additional_context else "Aucun contexte additionnel"
    
    inputs = {
        "task_title": task_title,
        "task_description": task_description,
        "task_type": task_type,
        "additional_context": context_str
    }
    
    # Créer le callback pour enregistrer les interactions IA
    callbacks = []
    if run_step_id:
        from utils.langchain_db_callback import create_db_callback
        callbacks = [create_db_callback(run_step_id)]
        logger.debug(f"📝 Callback DB activé pour run_step_id={run_step_id}")
    
    # Tentative avec le provider principal
    try:
        logger.info(f"🚀 Génération plan avec {provider}...")
        chain = create_implementation_plan_chain(provider=provider)
        plan = await chain.ainvoke(inputs, config={"callbacks": callbacks})
        
        logger.info(f"✅ Plan généré avec succès: {len(plan.steps)} étapes, complexité={plan.total_estimated_complexity}")
        return plan
        
    except Exception as e:
        logger.warning(f"⚠️ Échec génération plan avec {provider}: {e}")
        
        # Fallback vers OpenAI si configuré
        if fallback_to_openai and provider.lower() != "openai":
            try:
                logger.info("🔄 Fallback vers OpenAI...")
                chain_fallback = create_implementation_plan_chain(provider="openai")
                plan = await chain_fallback.ainvoke(inputs, config={"callbacks": callbacks})
                
                logger.info(f"✅ Plan généré avec succès (fallback OpenAI): {len(plan.steps)} étapes")
                return plan
                
            except Exception as fallback_error:
                logger.error(f"❌ Fallback OpenAI échoué: {fallback_error}")
                raise Exception(f"Tous les providers ont échoué. Principal: {e}, Fallback: {fallback_error}")
        
        # Pas de fallback configuré
        raise Exception(f"Génération plan échouée avec {provider}: {e}")


def extract_plan_metrics(plan: ImplementationPlan) -> Dict[str, Any]:
    """
    Extrait les métriques d'un plan d'implémentation.
    
    Args:
        plan: Plan d'implémentation validé
        
    Returns:
        Dictionnaire de métriques
    """
    high_risk_steps = [s for s in plan.steps if s.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]
    files_to_modify = set()
    for step in plan.steps:
        files_to_modify.update(step.files_to_modify)
    
    return {
        "total_steps": len(plan.steps),
        "total_complexity": plan.total_estimated_complexity,
        "average_complexity": plan.total_estimated_complexity / len(plan.steps) if plan.steps else 0,
        "high_risk_steps_count": len(high_risk_steps),
        "high_risk_steps_percentage": (len(high_risk_steps) / len(plan.steps) * 100) if plan.steps else 0,
        "total_files_to_modify": len(files_to_modify),
        "total_blockers": len(plan.potential_blockers),
        "has_critical_risks": any(s.risk_level == RiskLevel.CRITICAL for s in plan.steps)
    }

