"""Router pour la validation humaine des codes générés."""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel

from models.schemas import (
    HumanValidationRequest,
    HumanValidationResponse, 
    HumanValidationStatus,
    HumanValidationSummary
)
from services.human_validation_service import validation_service
from utils.logger import get_logger
from config.langsmith_config import langsmith_config

logger = get_logger(__name__)

# Créer le router
human_validation_router = APIRouter()


# Modèles de requête/réponse pour l'API
class ValidationApprovalRequest(BaseModel):
    """Requête d'approbation de validation."""
    validation_id: str
    comments: Optional[str] = None
    approval_notes: Optional[str] = None
    validated_by: Optional[str] = None


class ValidationRejectionRequest(BaseModel):
    """Requête de rejet de validation."""
    validation_id: str
    comments: str  # Obligatoire pour expliquer le rejet
    suggested_changes: Optional[str] = None
    validated_by: Optional[str] = None


class ValidationListResponse(BaseModel):
    """Réponse de liste des validations."""
    validations: List[HumanValidationSummary]
    total_count: int
    pending_count: int
    expired_count: int


@human_validation_router.get("/pending", response_model=ValidationListResponse)
async def get_pending_validations(
    limit: int = Query(50, ge=1, le=100, description="Nombre maximum de validations à retourner"),
    offset: int = Query(0, ge=0, description="Décalage pour la pagination"),
    include_expired: bool = Query(False, description="Inclure les validations expirées")
):
    """
    Récupère la liste des validations en attente.
    
    Args:
        limit: Nombre maximum de validations à retourner
        offset: Décalage pour la pagination
        include_expired: Inclure les validations expirées
        
    Returns:
        Liste des validations avec métadonnées
    """
    logger.info(f"📋 Récupération des validations en attente (limit={limit}, offset={offset})")
    
    try:
        # Récupérer les validations via le service
        all_validations = await validation_service.list_pending_validations(include_expired)
        
        # Pagination
        total_count = len(all_validations)
        pending_count = len([v for v in all_validations if v.status == HumanValidationStatus.PENDING])
        expired_count = len([v for v in all_validations if v.status == HumanValidationStatus.EXPIRED])
        
        paginated_validations = all_validations[offset:offset + limit]
        
        return ValidationListResponse(
            validations=paginated_validations,
            total_count=total_count,
            pending_count=pending_count,
            expired_count=expired_count
        )
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération des validations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des validations: {str(e)}"
        )


@human_validation_router.get("/{validation_id}", response_model=HumanValidationRequest)
async def get_validation_details(validation_id: str):
    """
    Récupère les détails d'une validation spécifique.
    
    Args:
        validation_id: ID de la validation
        
    Returns:
        Détails complets de la validation
    """
    logger.info(f"📄 Récupération détails validation: {validation_id}")
    
    validation = await validation_service.get_validation_by_id(validation_id)
    
    if not validation:
        logger.warning(f"⚠️ Validation non trouvée: {validation_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Validation {validation_id} non trouvée"
        )
    
    # Vérifier si expirée
    if validation.expires_at and validation.expires_at < datetime.now():
        logger.warning(f"⏰ Validation expirée: {validation_id}")
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Validation {validation_id} expirée"
        )
    
    return validation


@human_validation_router.post("/{validation_id}/approve", response_model=dict)
async def approve_validation(validation_id: str, request: ValidationApprovalRequest):
    """
    Approuve une validation humaine.
    
    Args:
        validation_id: ID de la validation
        request: Données d'approbation
        
    Returns:
        Confirmation de l'approbation
    """
    logger.info(f"✅ Approbation validation: {validation_id}")
    
    # Vérifier que la validation existe
    validation = await validation_service.get_validation_by_id(validation_id)
    if not validation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Validation {validation_id} non trouvée"
        )
    
    # Vérifier l'expiration
    if validation.expires_at and validation.expires_at < datetime.now():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Validation {validation_id} expirée"
        )
    
    try:
        # Créer la réponse d'approbation
        response = HumanValidationResponse(
            validation_id=validation_id,
            status=HumanValidationStatus.APPROVED,
            comments=request.comments,
            approval_notes=request.approval_notes,
            validated_by=request.validated_by,
            should_merge=True,
            should_continue_workflow=True
        )
        
        # Soumettre la réponse
        success = await validation_service.submit_validation_response(validation_id, response)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la soumission de l'approbation"
            )
        
        # Tracer avec LangSmith
        if langsmith_config.client:
            try:
                langsmith_config.client.create_run(
                    name="human_validation_approved",
                    run_type="tool",
                    inputs={
                        "validation_id": validation_id,
                        "task_title": validation.task_title,
                        "validated_by": request.validated_by
                    },
                    outputs={
                        "status": "approved",
                        "has_comments": bool(request.comments),
                        "should_merge": True
                    },
                    extra={
                        "workflow_id": validation.workflow_id,
                        "human_validation": True,
                        "action": "approve"
                    }
                )
            except Exception as e:
                logger.warning(f"⚠️ Erreur LangSmith tracing: {e}")
        
        logger.info(f"✅ Validation {validation_id} approuvée par {request.validated_by}")
        
        return {
            "message": f"Validation {validation_id} approuvée avec succès",
            "validation_id": validation_id,
            "status": "approved",
            "validated_by": request.validated_by,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'approbation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'approbation: {str(e)}"
        )


@human_validation_router.post("/{validation_id}/reject", response_model=dict)
async def reject_validation(validation_id: str, request: ValidationRejectionRequest):
    """
    Rejette une validation humaine.
    
    Args:
        validation_id: ID de la validation
        request: Données de rejet
        
    Returns:
        Confirmation du rejet
    """
    logger.info(f"❌ Rejet validation: {validation_id}")
    
    # Vérifier que la validation existe
    validation = await validation_service.get_validation_by_id(validation_id)
    if not validation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Validation {validation_id} non trouvée"
        )
    
    try:
        # Créer la réponse de rejet
        response = HumanValidationResponse(
            validation_id=validation_id,
            status=HumanValidationStatus.REJECTED,
            comments=request.comments,
            suggested_changes=request.suggested_changes,
            validated_by=request.validated_by,
            should_merge=False,
            should_continue_workflow=True  # Continuer pour update Monday
        )
        
        # Soumettre la réponse
        success = await validation_service.submit_validation_response(validation_id, response)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la soumission du rejet"
            )
        
        # Tracer avec LangSmith
        if langsmith_config.client:
            try:
                langsmith_config.client.create_run(
                    name="human_validation_rejected",
                    run_type="tool",
                    inputs={
                        "validation_id": validation_id,
                        "task_title": validation.task_title,
                        "validated_by": request.validated_by,
                        "rejection_reason": request.comments
                    },
                    outputs={
                        "status": "rejected",
                        "has_suggestions": bool(request.suggested_changes),
                        "should_merge": False
                    },
                    extra={
                        "workflow_id": validation.workflow_id,
                        "human_validation": True,
                        "action": "reject"
                    }
                )
            except Exception as e:
                logger.warning(f"⚠️ Erreur LangSmith tracing: {e}")
        
        logger.info(f"❌ Validation {validation_id} rejetée par {request.validated_by}")
        
        return {
            "message": f"Validation {validation_id} rejetée",
            "validation_id": validation_id,
            "status": "rejected",
            "validated_by": request.validated_by,
            "comments": request.comments,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du rejet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du rejet: {str(e)}"
        )


@human_validation_router.get("/stats/summary", response_model=dict)
async def get_validation_stats():
    """
    Récupère les statistiques des validations.
    
    Returns:
        Statistiques globales des validations
    """
    logger.info("📊 Récupération statistiques validations")
    
    try:
        # Utiliser la fonction de statistiques du service
        stats = await validation_service.get_validation_stats()
        return stats
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération des statistiques: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des statistiques: {str(e)}"
        ) 