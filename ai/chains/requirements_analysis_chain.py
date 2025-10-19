"""Chaîne LangChain pour l'analyse structurée des requirements."""

import os
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


class TaskComplexity(str, Enum):
    """Niveau de complexité d'une tâche."""
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class RiskLevel(str, Enum):
    """Niveau de risque identifié."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FileValidationStatus(str, Enum):
    """Statut de validation d'un fichier."""
    VALID = "valid"
    NOT_FOUND = "not_found"
    UNCERTAIN = "uncertain"


class CandidateFile(BaseModel):
    """Fichier candidat pour modification."""
    path: str = Field(description="Chemin du fichier")
    action: str = Field(description="Action à effectuer (create, modify, delete)")
    reason: str = Field(description="Raison de la modification")
    validation_status: FileValidationStatus = Field(
        default=FileValidationStatus.UNCERTAIN,
        description="Statut de validation du fichier"
    )


class TaskDependency(BaseModel):
    """Dépendance identifiée pour la tâche."""
    name: str = Field(description="Nom de la dépendance")
    type: str = Field(description="Type (package, service, file, etc.)")
    version: Optional[str] = Field(default=None, description="Version requise si applicable")
    required: bool = Field(default=True, description="Si la dépendance est obligatoire")


class IdentifiedRisk(BaseModel):
    """Risque identifié lors de l'analyse."""
    description: str = Field(description="Description du risque")
    level: RiskLevel = Field(description="Niveau de gravité du risque")
    mitigation: str = Field(description="Stratégie de mitigation proposée")
    probability: int = Field(ge=1, le=10, description="Probabilité d'occurrence (1-10)")


class Ambiguity(BaseModel):
    """Ambiguïté identifiée dans les requirements."""
    question: str = Field(description="Question ou point ambigu")
    impact: str = Field(description="Impact de cette ambiguïté")
    suggested_assumption: Optional[str] = Field(
        default=None,
        description="Hypothèse suggérée si pas de clarification"
    )


class RequirementsAnalysis(BaseModel):
    """Modèle Pydantic pour l'analyse complète des requirements."""
    schema_version: int = Field(default=1, description="Version du schéma")

    task_summary: str = Field(description="Résumé de la tâche analysée")

    complexity: TaskComplexity = Field(description="Complexité estimée de la tâche")
    complexity_score: int = Field(
        ge=1,
        le=10,
        description="Score de complexité (1=très simple, 10=très complexe)"
    )

    estimated_duration_minutes: int = Field(
        ge=5,
        description="Durée estimée en minutes"
    )

    candidate_files: List[CandidateFile] = Field(
        default_factory=list,
        description="Fichiers identifiés pour modification"
    )

    dependencies: List[TaskDependency] = Field(
        default_factory=list,
        description="Dépendances identifiées"
    )

    risks: List[IdentifiedRisk] = Field(
        default_factory=list,
        description="Risques identifiés"
    )

    ambiguities: List[Ambiguity] = Field(
        default_factory=list,
        description="Ambiguïtés ou points nécessitant clarification"
    )

    missing_info: List[str] = Field(
        default_factory=list,
        description="Informations manquantes pour une implémentation optimale"
    )

    implementation_approach: str = Field(
        description="Approche d'implémentation recommandée"
    )

    test_strategy: str = Field(
        description="Stratégie de test recommandée"
    )

    breaking_changes_risk: bool = Field(
        default=False,
        description="Si l'implémentation risque de casser du code existant"
    )

    requires_external_deps: bool = Field(
        default=False,
        description="Si l'implémentation nécessite des dépendances externes"
    )

    quality_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Score de qualité de l'analyse (coverage)"
    )

    class Config:
        """Configuration Pydantic."""
        json_schema_extra = {
            "example": {
                "schema_version": 1,
                "task_summary": "Créer une API REST pour gérer les utilisateurs",
                "complexity": "moderate",
                "complexity_score": 6,
                "estimated_duration_minutes": 45,
                "candidate_files": [
                    {
                        "path": "api/routes/users.py",
                        "action": "create",
                        "reason": "Nouvelles routes API utilisateurs",
                        "validation_status": "uncertain"
                    }
                ],
                "dependencies": [
                    {
                        "name": "fastapi",
                        "type": "package",
                        "version": ">=0.104.0",
                        "required": True
                    }
                ],
                "risks": [
                    {
                        "description": "Conflit avec routes existantes",
                        "level": "medium",
                        "mitigation": "Vérifier les routes avant implémentation",
                        "probability": 5
                    }
                ],
                "ambiguities": [],
                "missing_info": ["Schéma de validation exact pour User"],
                "implementation_approach": "Créer module API séparé avec validation Pydantic",
                "test_strategy": "Tests unitaires + tests d'intégration API",
                "breaking_changes_risk": False,
                "requires_external_deps": False,
                "quality_score": 0.85
            }
        }


def create_requirements_analysis_chain(
    provider: str = "anthropic",
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 4000,
    max_retries: int = 2
):
    """
    Crée une chaîne LCEL pour analyser les requirements de manière structurée.

    Args:
        provider: Provider LLM à utiliser ("anthropic" ou "openai")
        model: Nom du modèle (optionnel, utilise le défaut du provider)
        temperature: Température du modèle (0.0-1.0)
        max_tokens: Nombre maximum de tokens
        max_retries: Nombre de tentatives en cas d'échec de validation

    Returns:
        Chaîne LCEL configurée (Prompt → LLM → Parser)

    Raises:
        ValueError: Si le provider n'est pas supporté
        Exception: Si les clés API sont manquantes
    """
    logger.info(f"🔗 Création requirements_analysis_chain avec provider={provider}")

    # 1. Créer le parser Pydantic
    parser = PydanticOutputParser(pydantic_object=RequirementsAnalysis)

    # 2. Créer le prompt template avec instructions de formatage
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """Tu es un analyste technique expert qui analyse les requirements de projets logiciels.
Tu dois examiner la description de la tâche et générer une analyse structurée complète au format JSON strict.

IMPORTANT: Tu DOIS retourner UNIQUEMENT du JSON valide, sans texte avant ou après.
Utilise le schéma suivant:

{format_instructions}

Sois exhaustif dans ton analyse :
- Identifie TOUS les fichiers potentiellement concernés
- Liste TOUTES les dépendances nécessaires
- Détecte TOUS les risques possibles
- Signale TOUTES les ambiguïtés ou informations manquantes
- Estime la complexité de façon réaliste
- Propose une stratégie d'implémentation claire

✅ RÈGLES IMPORTANTES pour réduire les informations manquantes :
1. Si une information n'est pas fournie, propose une valeur par défaut raisonnable
2. Pour les critères d'acceptation manquants, déduis-les du titre et de la description
3. Pour le contexte technique manquant, assume un contexte standard selon le type de projet
4. Pour les dépendances, liste les dépendances courantes même si non mentionnées explicitement
5. Privilégie des estimations conservatrices plutôt que de signaler des manques"""),
        ("user", """Analyse cette tâche en détail:

## INFORMATIONS DE LA TÂCHE

**Titre**: {task_title}
**Type**: {task_type}
**Priorité**: {priority}

**Description**:
{description}

**Critères d'acceptation**:
{acceptance_criteria}

**Contexte technique**:
{technical_context}

**Fichiers mentionnés**:
{files_to_modify}

**Repository**: {repository_url}

## CONTEXTE ADDITIONNEL
{additional_context}

Génère une analyse complète et structurée de cette tâche.""")
    ])

    # 3. Injecter les instructions de formatage du parser dans le prompt
    prompt = prompt_template.partial(format_instructions=parser.get_format_instructions())

    # 4. Créer le LLM selon le provider avec retry
    if provider.lower() == "anthropic":
        if not settings.anthropic_api_key:
            raise Exception("ANTHROPIC_API_KEY manquante dans la configuration")

        llm = ChatAnthropic(
            model=model or "claude-3-5-sonnet-20241022",
            anthropic_api_key=settings.anthropic_api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries
        )
        logger.info(f"✅ LLM Anthropic initialisé: {model or 'claude-3-5-sonnet-20241022'}")

    elif provider.lower() == "openai":
        if not settings.openai_api_key:
            raise Exception("OPENAI_API_KEY manquante dans la configuration")

        llm = ChatOpenAI(
            model=model or "gpt-4",
            openai_api_key=settings.openai_api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries
        )
        logger.info(f"✅ LLM OpenAI initialisé: {model or 'gpt-4'}")

    else:
        raise ValueError(f"Provider non supporté: {provider}. Utilisez 'anthropic' ou 'openai'")

    # 5. Créer la chaîne LCEL: Prompt → LLM → Parser
    chain = prompt | llm | parser

    logger.info("✅ Requirements analysis chain créée avec succès")
    return chain


async def generate_requirements_analysis(
    task_title: str,
    task_description: str,
    task_type: str = "feature",
    priority: str = "medium",
    acceptance_criteria: Optional[str] = None,
    technical_context: Optional[str] = None,
    files_to_modify: Optional[List[str]] = None,
    repository_url: Optional[str] = None,
    additional_context: Optional[Dict[str, Any]] = None,
    provider: str = "anthropic",
    fallback_to_openai: bool = True,
    validate_files: bool = True,
    run_step_id: Optional[int] = None
) -> RequirementsAnalysis:
    """
    Génère une analyse structurée des requirements avec fallback automatique.

    Args:
        task_title: Titre de la tâche
        task_description: Description détaillée
        task_type: Type de tâche (feature, bugfix, refactor, etc.)
        priority: Priorité de la tâche
        acceptance_criteria: Critères d'acceptation
        technical_context: Contexte technique additionnel
        files_to_modify: Liste des fichiers à modifier (si connus)
        repository_url: URL du repository
        additional_context: Contexte additionnel (dict)
        provider: Provider principal ("anthropic" ou "openai")
        fallback_to_openai: Si True, fallback vers OpenAI si le provider principal échoue
        validate_files: Si True, valide l'existence des fichiers candidats

    Returns:
        RequirementsAnalysis validé par Pydantic

    Raises:
        Exception: Si tous les providers échouent
    """
    # Préparer les inputs
    context_str = str(additional_context) if additional_context else "Aucun contexte additionnel"
    files_str = ", ".join(files_to_modify) if files_to_modify else "Non spécifiés"

    inputs = {
        "task_title": task_title,
        "description": task_description,
        "task_type": task_type,
        "priority": priority,
        "acceptance_criteria": acceptance_criteria or "Non spécifiés",
        "technical_context": technical_context or "Non spécifié",
        "files_to_modify": files_str,
        "repository_url": repository_url or "Non spécifié",
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
        logger.info(f"🚀 Génération analyse requirements avec {provider}...")
        chain = create_requirements_analysis_chain(provider=provider)
        analysis = await chain.ainvoke(inputs, config={"callbacks": callbacks})

        # Post-traitement: validation des fichiers
        if validate_files and analysis.candidate_files:
            _validate_candidate_files(analysis.candidate_files)

        # Calculer le score de qualité
        analysis.quality_score = _calculate_quality_score(analysis)

        logger.info(
            f"✅ Analyse générée avec succès: "
            f"{len(analysis.candidate_files)} fichiers, "
            f"{len(analysis.risks)} risques, "
            f"{len(analysis.ambiguities)} ambiguïtés, "
            f"quality_score={analysis.quality_score:.2f}"
        )
        return analysis

    except Exception as e:
        logger.warning(f"⚠️ Échec génération analyse avec {provider}: {e}")

        # Fallback vers OpenAI si configuré
        if fallback_to_openai and provider.lower() != "openai":
            try:
                logger.info("🔄 Fallback vers OpenAI...")
                chain_fallback = create_requirements_analysis_chain(provider="openai")
                analysis = await chain_fallback.ainvoke(inputs, config={"callbacks": callbacks})

                if validate_files and analysis.candidate_files:
                    _validate_candidate_files(analysis.candidate_files)

                analysis.quality_score = _calculate_quality_score(analysis)

                logger.info("✅ Analyse générée avec succès (fallback OpenAI)")
                return analysis

            except Exception as fallback_error:
                logger.error(f"❌ Fallback OpenAI échoué: {fallback_error}")
                raise Exception(
                    f"Tous les providers ont échoué. "
                    f"Principal: {e}, Fallback: {fallback_error}"
                )

        # Pas de fallback configuré
        raise Exception(f"Génération analyse échouée avec {provider}: {e}")


def _validate_candidate_files(files: List[CandidateFile]):
    """
    Valide l'existence des fichiers candidats.

    Args:
        files: Liste des fichiers candidats à valider
    """
    for file in files:
        # Ne valider que les fichiers qui doivent exister (modify, delete)
        if file.action in ["modify", "delete"]:
            if os.path.exists(file.path):
                file.validation_status = FileValidationStatus.VALID
            else:
                file.validation_status = FileValidationStatus.NOT_FOUND
                logger.warning(f"⚠️ Fichier non trouvé: {file.path}")
        elif file.action == "create":
            # Pour les créations, vérifier que le fichier n'existe pas déjà
            if os.path.exists(file.path):
                file.validation_status = FileValidationStatus.UNCERTAIN
                logger.warning(f"⚠️ Fichier à créer existe déjà: {file.path}")
            else:
                file.validation_status = FileValidationStatus.VALID


def _calculate_quality_score(analysis: RequirementsAnalysis) -> float:
    """
    Calcule un score de qualité pour l'analyse.

    ✅ AMÉLIORATION: Seuil de qualité augmenté (0.70 → 0.80)

    Le score est basé sur:
    - Présence et validité des fichiers candidats
    - Identification de risques
    - Gestion des dépendances
    - Complétude de l'analyse
    - Clarté des requirements (pénalités pour ambiguïtés)

    Args:
        analysis: Analyse à évaluer

    Returns:
        Score entre 0.0 et 1.0 (minimum recommandé: 0.80)
    """
    score = 0.0

    # ✅ Points pour les fichiers candidats (max 0.35, augmenté de 0.30)
    if analysis.candidate_files:
        valid_files = sum(
            1 for f in analysis.candidate_files
            if f.validation_status == FileValidationStatus.VALID
        )
        uncertain_files = sum(
            1 for f in analysis.candidate_files
            if f.validation_status == FileValidationStatus.UNCERTAIN
        )
        total_files = len(analysis.candidate_files)

        # ✅ FIX: Si tous les fichiers sont UNCERTAIN (pas encore validés), donner un score partiel
        if uncertain_files == total_files:
            # Repository pas encore cloné, donner crédit pour avoir identifié les fichiers
            file_score = 0.30  # Score partiel pour identification
            logger.info(f"📋 {total_files} fichiers identifiés (validation en attente)")
        else:
            # Bonus si tous les fichiers sont valides
            file_score = (valid_files / total_files) * 0.35
            if valid_files == total_files and total_files >= 2:
                file_score += 0.05  # Bonus pour analyse complète

        score += min(0.40, file_score)
    else:
        # ✅ NOUVEAU: Pénalité si aucun fichier identifié
        logger.warning("⚠️ Aucun fichier candidat identifié - qualité réduite")

    # ✅ Points pour l'identification de risques (max 0.15)
    if analysis.risks:
        # Favoriser une analyse équilibrée des risques
        risk_score = min(0.15, len(analysis.risks) * 0.04)
        score += risk_score

    # ✅ Points pour les dépendances (max 0.15)
    if analysis.dependencies:
        dep_score = min(0.15, len(analysis.dependencies) * 0.04)
        score += dep_score

    # ✅ Points pour la complétude (max 0.40, augmenté de 0.30)
    completeness = 0.0
    if analysis.implementation_approach and len(analysis.implementation_approach) > 20:
        completeness += 0.15  # Augmenté de 0.10
    if analysis.test_strategy and len(analysis.test_strategy) > 15:
        completeness += 0.15  # Augmenté de 0.10
    if analysis.estimated_duration_minutes > 0:
        completeness += 0.10
    score += completeness

    # ✅ NOUVEAU: Pénalités pour réduire la qualité si ambiguïtés ou infos manquantes
    penalties = 0.0

    # Pénalité pour ambiguïtés excessives
    if analysis.ambiguities and len(analysis.ambiguities) > 3:
        penalties += min(0.10, (len(analysis.ambiguities) - 3) * 0.03)
        logger.warning(f"⚠️ {len(analysis.ambiguities)} ambiguïtés détectées - pénalité appliquée")

    # Pénalité pour informations manquantes critiques (✅ AMÉLIORATION: Plus tolérant)
    if analysis.missing_info and len(analysis.missing_info) > 4:  # Augmenté de 2 à 4
        penalties += min(0.08, (len(analysis.missing_info) - 4) * 0.02)  # Pénalité réduite
        logger.warning(f"⚠️ {len(analysis.missing_info)} informations manquantes - pénalité réduite appliquée")

    # Appliquer les pénalités
    score = max(0.0, score - penalties)

    # ✅ AMÉLIORATION: Seuil de qualité plus tolérant et logging amélioré
    final_score = min(1.0, score)
    if final_score < 0.75:  # Seuil réduit de 0.80 à 0.75
        logger.warning(
            f"⚠️ Score de qualité insuffisant: {final_score:.2f} < 0.75 "
            f"(fichiers: {len(analysis.candidate_files) if analysis.candidate_files else 0}, "
            f"ambiguïtés: {len(analysis.ambiguities)}, "
            f"infos manquantes: {len(analysis.missing_info)})"
        )
    elif final_score < 0.85:
        logger.info(
            f"📊 Score de qualité acceptable: {final_score:.2f} "
            f"(fichiers: {len(analysis.candidate_files) if analysis.candidate_files else 0}, "
            f"ambiguïtés: {len(analysis.ambiguities)}, "
            f"infos manquantes: {len(analysis.missing_info)})"
        )

    return final_score


def extract_analysis_metrics(analysis: RequirementsAnalysis) -> Dict[str, Any]:
    """
    Extrait les métriques d'une analyse de requirements.

    Args:
        analysis: Analyse validée

    Returns:
        Dictionnaire de métriques
    """
    valid_files = sum(
        1 for f in analysis.candidate_files
        if f.validation_status == FileValidationStatus.VALID
    )

    high_risks = sum(
        1 for r in analysis.risks
        if r.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
    )

    return {
        "schema_version": analysis.schema_version,
        "complexity": analysis.complexity.value,
        "complexity_score": analysis.complexity_score,
        "estimated_duration_minutes": analysis.estimated_duration_minutes,
        "total_files": len(analysis.candidate_files),
        "valid_files": valid_files,
        "invalid_files": len(analysis.candidate_files) - valid_files,
        "file_coverage": valid_files / len(analysis.candidate_files) if analysis.candidate_files else 0,
        "total_dependencies": len(analysis.dependencies),
        "required_dependencies": sum(1 for d in analysis.dependencies if d.required),
        "total_risks": len(analysis.risks),
        "high_risks": high_risks,
        "risk_percentage": (high_risks / len(analysis.risks) * 100) if analysis.risks else 0,
        "total_ambiguities": len(analysis.ambiguities),
        "missing_info_count": len(analysis.missing_info),
        "quality_score": analysis.quality_score or 0.0,
        "breaking_changes_risk": analysis.breaking_changes_risk,
        "requires_external_deps": analysis.requires_external_deps
    }
