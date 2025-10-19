"""Service d'analyse intelligente des réponses humaines avec système hybride."""

import openai
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from utils.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class IntentionType(Enum):
    """Types d'intention détectés."""
    APPROVE = "approved"  # Corrigé: approve -> approved pour correspondre à la DB
    REJECT = "rejected"   # Corrigé: reject -> rejected pour correspondre à la DB
    QUESTION = "question"
    UNCLEAR = "unclear"
    CLARIFICATION_NEEDED = "clarification_needed"


class ConfidenceLevel(Enum):
    """Niveaux de confiance."""
    HIGH = "high"      # 0.8-1.0
    MEDIUM = "medium"  # 0.5-0.8
    LOW = "low"        # 0.0-0.5


@dataclass
class ValidationDecision:
    """Résultat de l'analyse d'intention."""
    decision: IntentionType
    confidence: float
    reasoning: str
    specific_concerns: List[str]
    suggested_action: str
    requires_clarification: bool
    analysis_method: str
    raw_reply: str
    timestamp: datetime


class IntelligentReplyAnalyzer:
    """Analyseur intelligent des réponses humaines avec escalade progressive."""
    
    def __init__(self):
        self.openai_client = None
        self._init_openai_client()
        
        # Patterns pour analyse rapide (Niveau 1)
        self.quick_patterns = self._load_quick_patterns()
        
        # Seuils de confiance
        self.HIGH_CONFIDENCE_THRESHOLD = 0.8
        self.MEDIUM_CONFIDENCE_THRESHOLD = 0.5
    
    def _init_openai_client(self):
        """Initialise le client OpenAI si disponible."""
        try:
            if settings.openai_api_key:
                self.openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
                logger.info("✅ Client OpenAI initialisé pour analyse sentiment")
            else:
                logger.warning("⚠️ Pas de clé OpenAI - analyse basique seulement")
        except Exception as e:
            logger.error(f"❌ Erreur init OpenAI client: {e}")
    
    async def analyze_human_intention(self, reply_text: str, context: Optional[Dict[str, Any]] = None) -> ValidationDecision:
        """
        Analyse l'intention humaine avec système hybride escaladé.
        
        Escalade progressive:
        1. Patterns simples (rapide, gratuit)
        2. Si ambigu → OpenAI (précis, payant)
        3. Si très ambigu → Demande clarification
        
        Args:
            reply_text: Texte de la réponse humaine
            context: Contexte optionnel (tâche, PR, etc.)
            
        Returns:
            ValidationDecision avec intention et confiance
        """
        logger.info(f"🧠 Analyse intention: '{reply_text[:50]}...'")
        
        # Nettoyage du texte
        cleaned_text = self._clean_text(reply_text)
        
        try:
            # NIVEAU 1: Patterns simples pour cas évidents
            simple_decision = await self._analyze_with_patterns(cleaned_text, context)
            
            if simple_decision.confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
                logger.info(f"✅ Décision simple confiance haute: {simple_decision.decision.value}")
                return simple_decision
            
            # NIVEAU 2: OpenAI pour cas ambigus (si disponible)
            if self.openai_client and simple_decision.confidence < self.HIGH_CONFIDENCE_THRESHOLD:
                logger.info("🤖 Escalade vers OpenAI pour analyse approfondie")
                openai_decision = await self._analyze_with_openai(cleaned_text, context, simple_decision)
                
                if openai_decision.confidence >= self.MEDIUM_CONFIDENCE_THRESHOLD:
                    logger.info(f"✅ Décision OpenAI confiance suffisante: {openai_decision.decision.value}")
                    return openai_decision
            
            # NIVEAU 3: Cas très ambigus - demander clarification
            if simple_decision.confidence < self.MEDIUM_CONFIDENCE_THRESHOLD:
                logger.warning("⚠️ Réponse très ambiguë - clarification requise")
                return ValidationDecision(
                    decision=IntentionType.CLARIFICATION_NEEDED,
                    confidence=simple_decision.confidence,
                    reasoning="Réponse ambiguë - clarification humaine requise",
                    specific_concerns=["ambiguity", "unclear_intent"],
                    suggested_action="request_clarification",
                    requires_clarification=True,
                    analysis_method="escalation_level_3",
                    raw_reply=reply_text,
                    timestamp=datetime.now()
                )
            
            # Fallback sur décision simple
            logger.info(f"📋 Utilisation décision simple par défaut: {simple_decision.decision.value}")
            return simple_decision
            
        except Exception as e:
            logger.error(f"❌ Erreur analyse intention: {e}")
            return self._create_error_decision(reply_text, str(e))
    
    async def _analyze_with_patterns(self, text: str, context: Optional[Dict[str, Any]]) -> ValidationDecision:
        """Analyse avec patterns rapides (Niveau 1)."""
        
        # Calcul des scores pour chaque intention
        approval_score = self._calculate_pattern_score(text, self.quick_patterns["approval"])
        rejection_score = self._calculate_pattern_score(text, self.quick_patterns["rejection"])
        question_score = self._calculate_pattern_score(text, self.quick_patterns["question"])
        
        # Ajustements contextuels
        if context:
            approval_score = self._adjust_score_with_context(approval_score, context, "approval")
            rejection_score = self._adjust_score_with_context(rejection_score, context, "rejection")
        
        # Détermination de l'intention principale
        max_score = max(approval_score, rejection_score, question_score)
        
        if max_score == approval_score and approval_score > 0.3:
            decision = IntentionType.APPROVE
            confidence = min(approval_score, 0.95)  # Cap à 95% pour patterns
        elif max_score == rejection_score and rejection_score > 0.3:
            decision = IntentionType.REJECT
            confidence = min(rejection_score, 0.95)
        elif max_score == question_score and question_score > 0.4:
            decision = IntentionType.QUESTION
            confidence = min(question_score, 0.8)
        else:
            decision = IntentionType.UNCLEAR
            confidence = max_score
        
        # Identification des préoccupations spécifiques
        concerns = self._identify_specific_concerns(text)
        
        # Action suggérée
        suggested_action = self._suggest_action(decision, concerns, confidence)
        
        return ValidationDecision(
            decision=decision,
            confidence=confidence,
            reasoning=f"Pattern analysis: max_score={max_score:.2f}, concerns={len(concerns)}",
            specific_concerns=concerns,
            suggested_action=suggested_action,
            requires_clarification=confidence < self.MEDIUM_CONFIDENCE_THRESHOLD,
            analysis_method="pattern_based_level_1",
            raw_reply=text,
            timestamp=datetime.now()
        )
    
    async def _analyze_with_openai(self, text: str, context: Optional[Dict[str, Any]], fallback_decision: ValidationDecision) -> ValidationDecision:
        """Analyse avec OpenAI (Niveau 2)."""
        
        try:
            # Construire le prompt contextuel
            prompt = self._build_openai_prompt(text, context, fallback_decision)
            
            # Appel OpenAI
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",  # Plus rapide et moins cher que GPT-4
                messages=[
                    {
                        "role": "system",
                        "content": """Tu es un expert en analyse d'intention pour validation de code.
                        Analyse la réponse humaine et retourne un JSON avec:
                        - decision: "approve", "reject", "question", ou "unclear"
                        - confidence: float entre 0 et 1
                        - reasoning: explication courte
                        - concerns: liste des préoccupations identifiées
                        - urgent: boolean si c'est urgent"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Peu de créativité, focus précision
                max_tokens=300
            )
            
            # Parser la réponse OpenAI
            openai_analysis = self._parse_openai_response(response.choices[0].message.content)
            
            # Combiner avec l'analyse de patterns
            final_decision = self._merge_analyses(fallback_decision, openai_analysis, text)
            
            logger.info(f"🤖 OpenAI analyse terminée: {final_decision.decision.value} (conf: {final_decision.confidence:.2f})")
            return final_decision
            
        except Exception as e:
            logger.error(f"❌ Erreur OpenAI analyse: {e}")
            # Fallback sur l'analyse de patterns
            fallback_decision.analysis_method = "pattern_fallback_after_openai_error"
            fallback_decision.reasoning += f" (OpenAI error: {str(e)[:50]})"
            return fallback_decision
    
    def _load_quick_patterns(self) -> Dict[str, List[Tuple[str, float]]]:
        """Charge les patterns rapides avec leurs poids."""
        
        return {
            "approval": [
                # Patterns d'approbation avec poids
                (r'\b(oui|yes|ok|go|ship)\b', 0.9),
                (r'\b(parfait|excellent|good|great|lgtm)\b', 0.8),
                (r'\b(valide|approve|accept|merge)\b', 0.95),
                (r'\b(deploy|release|publish)\b', 0.85),
                (r'[✅✓👍]', 0.9),
                (r'^(oui|yes|ok)[\s\.,!]*$', 0.95),  # Réponses courtes claires
                (r'\b(continue|proceed|go ahead)\b', 0.8),
                (r'\+1', 0.85),
            ],
            "rejection": [
                # Patterns de rejet avec poids
                (r'\b(non|no|stop|halt|wait)\b', 0.9),
                (r'\b(problème|problem|issue|bug|erreur|error)\b', 0.85),
                (r'\b(refais|redo|fix|debug|correct)\b', 0.9),
                (r'\b(refuse|reject|deny|cancel)\b', 0.95),
                (r'[❌✗👎]', 0.9),
                (r'^(non|no)[\s\.,!]*$', 0.95),  # Réponses courtes claires
                (r'\b(change|modify|update|revise)\b', 0.7),
                (r'-1', 0.85),
            ],
            "question": [
                # Patterns de questions avec poids
                (r'\?', 0.8),
                (r'\b(comment|how|pourquoi|why|what|quoi)\b', 0.7),
                (r'\b(peux-tu|can you|could you|pourrais-tu)\b', 0.8),
                (r'\b(expliquer|explain|clarify|préciser)\b', 0.85),
                (r'\b(que se passe|what happens|what about)\b', 0.8),
            ]
        }
    
    def _calculate_pattern_score(self, text: str, patterns: List[Tuple[str, float]]) -> float:
        """Calcule le score pour une catégorie de patterns."""
        
        score = 0.0
        text_lower = text.lower()
        
        for pattern, weight in patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            if matches:
                # Plus de matches = score plus élevé, mais avec diminution marginale
                match_boost = min(len(matches) * 0.1, 0.3)
                score += weight + match_boost
        
        # Normaliser le score (max 1.0)
        return min(score, 1.0)
    
    def _identify_specific_concerns(self, text: str) -> List[str]:
        """Identifie les préoccupations spécifiques mentionnées."""
        
        concerns = []
        text_lower = text.lower()
        
        concern_patterns = {
            "tests": r'\b(test|testing|spec|unittest)\b',
            "security": r'\b(security|secure|vulner|auth|permission)\b',
            "performance": r'\b(performance|speed|slow|fast|optim)\b',
            "documentation": r'\b(doc|documentation|comment|readme)\b',
            "style": r'\b(style|format|lint|prettier|code style)\b',
            "breaking_change": r'\b(breaking|break|compat|version)\b',
            "dependency": r'\b(depend|package|library|import)\b'
        }
        
        for concern, pattern in concern_patterns.items():
            if re.search(pattern, text_lower):
                concerns.append(concern)
        
        return concerns
    
    def _suggest_action(self, decision: IntentionType, concerns: List[str], confidence: float) -> str:
        """Suggère une action basée sur la décision et les préoccupations."""
        
        if decision == IntentionType.APPROVE:
            if confidence > 0.9:
                return "merge_immediately"
            elif "tests" in concerns:
                return "run_additional_tests_then_merge"
            else:
                return "merge_with_standard_checks"
        
        elif decision == IntentionType.REJECT:
            if "tests" in concerns:
                return "fix_tests_first"
            elif "security" in concerns:
                return "security_review_required"
            elif "performance" in concerns:
                return "performance_optimization_needed"
            else:
                return "address_concerns_then_resubmit"
        
        elif decision == IntentionType.QUESTION:
            return "provide_clarification"
        
        else:  # UNCLEAR
            if confidence < 0.3:
                return "request_explicit_approval_or_rejection"
            else:
                return "seek_additional_context"
    
    def _build_openai_prompt(self, text: str, context: Optional[Dict[str, Any]], fallback: ValidationDecision) -> str:
        """Construit le prompt pour OpenAI."""
        
        context_info = ""
        if context:
            context_info = f"""
CONTEXTE:
- Tâche: {context.get('task_title', 'N/A')}
- Type: {context.get('task_type', 'N/A')}
- Tests: {'✅ Réussis' if context.get('tests_passed') else '❌ Échoués'}
"""
        
        return f"""
Analyse cette réponse d'un humain qui valide du code:

RÉPONSE: "{text}"

{context_info}

ANALYSE PRÉLIMINAIRE:
- Décision patterns: {fallback.decision.value}
- Confiance: {fallback.confidence:.2f}
- Préoccupations: {fallback.specific_concerns}

Affine cette analyse. Retourne un JSON valide:
{{
    "decision": "approve|reject|question|unclear",
    "confidence": 0.85,
    "reasoning": "Explication courte",
    "concerns": ["tests", "security"],
    "urgent": false
}}
"""
    
    def _parse_openai_response(self, response_text: str) -> Dict[str, Any]:
        """Parse la réponse JSON d'OpenAI."""
        
        try:
            import json
            
            # Nettoyer la réponse (enlever les ```json si présents)
            cleaned = response_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            
            return json.loads(cleaned.strip())
            
        except Exception as e:
            logger.error(f"❌ Erreur parsing OpenAI response: {e}")
            return {
                "decision": "unclear",
                "confidence": 0.3,
                "reasoning": f"Erreur parsing: {str(e)}",
                "concerns": ["parsing_error"],
                "urgent": False
            }
    
    def _merge_analyses(self, pattern_analysis: ValidationDecision, openai_analysis: Dict[str, Any], original_text: str) -> ValidationDecision:
        """Merge les analyses patterns et OpenAI."""
        
        # Mapper les décisions OpenAI
        decision_map = {
            "approve": IntentionType.APPROVE,
            "reject": IntentionType.REJECT,
            "question": IntentionType.QUESTION,
            "unclear": IntentionType.UNCLEAR
        }
        
        openai_decision = decision_map.get(openai_analysis.get("decision", "unclear"), IntentionType.UNCLEAR)
        openai_confidence = float(openai_analysis.get("confidence", 0.5))
        
        # Stratégie de fusion:
        # Si OpenAI et patterns d'accord → haute confiance
        # Si désaccord → moyenne pondérée
        if openai_decision == pattern_analysis.decision:
            # Accord - booster la confiance
            final_confidence = min((pattern_analysis.confidence + openai_confidence) / 1.5, 0.98)
            final_decision = openai_decision
        else:
            # Désaccord - prendre la confiance la plus élevée
            if openai_confidence > pattern_analysis.confidence:
                final_decision = openai_decision
                final_confidence = openai_confidence * 0.9  # Légère pénalité pour désaccord
            else:
                final_decision = pattern_analysis.decision
                final_confidence = pattern_analysis.confidence * 0.9
        
        # Combiner les préoccupations
        combined_concerns = list(set(
            pattern_analysis.specific_concerns + 
            openai_analysis.get("concerns", [])
        ))
        
        return ValidationDecision(
            decision=final_decision,
            confidence=final_confidence,
            reasoning=f"Hybrid: patterns({pattern_analysis.confidence:.2f}) + OpenAI({openai_confidence:.2f}) = {openai_analysis.get('reasoning', 'N/A')}",
            specific_concerns=combined_concerns,
            suggested_action=self._suggest_action(final_decision, combined_concerns, final_confidence),
            requires_clarification=final_confidence < self.MEDIUM_CONFIDENCE_THRESHOLD,
            analysis_method="hybrid_patterns_plus_openai",
            raw_reply=original_text,
            timestamp=datetime.now()
        )
    
    def _adjust_score_with_context(self, score: float, context: Dict[str, Any], intention_type: str) -> float:
        """Ajuste le score selon le contexte."""
        
        # Si les tests ont échoué, boost les patterns de rejet
        if not context.get("tests_passed", True) and intention_type == "rejection":
            score *= 1.2
        
        # Si c'est urgent, boost les patterns d'approbation simples
        if context.get("urgent", False) and intention_type == "approval":
            score *= 1.1
        
        return min(score, 1.0)
    
    def _clean_text(self, text: str) -> str:
        """Nettoie le texte d'entrée."""
        
        # Enlever les caractères de formatage Monday.com
        cleaned = re.sub(r'<[^>]+>', '', text)  # Tags HTML
        cleaned = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', cleaned)  # Markdown bold
        cleaned = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', cleaned)  # Markdown italic
        cleaned = cleaned.strip()
        
        return cleaned
    
    def _create_error_decision(self, original_text: str, error_msg: str) -> ValidationDecision:
        """Crée une décision d'erreur par défaut."""
        
        return ValidationDecision(
            decision=IntentionType.UNCLEAR,
            confidence=0.1,
            reasoning=f"Erreur d'analyse: {error_msg}",
            specific_concerns=["analysis_error"],
            suggested_action="manual_review_required",
            requires_clarification=True,
            analysis_method="error_fallback",
            raw_reply=original_text,
            timestamp=datetime.now()
        )


# Instance globale
intelligent_reply_analyzer = IntelligentReplyAnalyzer() 