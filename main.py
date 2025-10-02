"""Point d'entrée principal de l'Agent d'Automatisation IA."""
import sys
import warnings
from typing import Dict, Optional

# ✅ SUPPRESSION des warnings LangChain Beta pour nettoyer les logs
try:
    from langchain_core._api.beta_decorator import LangChainBetaWarning
    warnings.simplefilter("ignore", LangChainBetaWarning)
except ImportError:
    # Fallback si l'import échoue
    warnings.filterwarnings("ignore", message="This API is in beta and may change in the future.")
from pydantic import BaseModel, Field, field_validator
from models.schemas import MondayColumnValue, TaskRequest, WebhookPayload
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from services.webhook_service import WebhookService
from services.webhook_persistence_service import webhook_persistence
from services.celery_app import celery_app, submit_task
from config.settings import get_settings
from utils.logger import get_logger

print("🔴 DEBUG: main.py est exécuté !")
print(f"🔴 DEBUG: Python path: {sys.path}")

logger = get_logger(__name__)

class MondayEvent(BaseModel):
    """Structure de l'evenement Monday.com dans le webhook."""
    pulseId: str = Field(..., description="ID de l'item Monday.com")
    boardId: str = Field(..., description="ID du board Monday.com")
    pulseName: str = Field(..., description="Nom/titre de l'item")
    columnValues: Dict[str, MondayColumnValue] = Field(default_factory=dict, description="Valeurs des colonnes")
    previousColumnValues: Optional[Dict[str, MondayColumnValue]] = Field(None, description="Anciennes valeurs")
    newColumnValues: Optional[Dict[str, MondayColumnValue]] = Field(None, description="Nouvelles valeurs")
    userId: Optional[int] = Field(None, description="ID de l'utilisateur qui a fait le changement")
    triggeredAt: Optional[str] = Field(None, description="Timestamp du déclenchement")
    
    @field_validator("pulseId", "boardId", mode="before")
    @classmethod
    def cast_to_str(cls, v):
        return str(v) if v is not None else v


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application."""
    logger.info("🚀 Démarrage de l'Agent d'Automatisation IA")
    
    # Démarrer le monitoring en arrière-plan
    try:
        await monitoring_service.start_monitoring()
        logger.info("✅ Service de monitoring démarré")
    except Exception as e:
        logger.error(f"❌ Erreur démarrage monitoring: {e}")
    
    yield
    
    # Arrêter proprement les services
    logger.info("🛑 Arrêt de l'Agent d'Automatisation IA")
    try:
        await monitoring_service.stop_monitoring()
        logger.info("✅ Service de monitoring arrêté")
    except Exception as e:
        logger.error(f"❌ Erreur arrêt monitoring: {e}")


# Initialiser l'application FastAPI
app = FastAPI(
    title="Agent d'Automatisation IA",
    description="Automatisation complète du cycle de développement avec IA",
    version="2.0.0",
    lifespan=lifespan
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, spécifier les domaines autorisés
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialiser les services
settings = get_settings()
webhook_service = WebhookService()

# Importer le service de monitoring
from services.monitoring_service import monitoring_service


@app.get("/")
async def root():
    """Point d'entree racine de l'API."""
    return {
        "message": "Agent d'Automatisation IA",
        "version": "2.0.0",
        "status": "running",
        "background_processing": "Celery",
        "documentation": "/docs"
    }


@app.get("/health")
async def health_check():
    """Verification de santé de l'application."""
    try:
        # Verifier la connexion Celery
        celery_status = celery_app.control.inspect().ping()
        celery_healthy = bool(celery_status)
        
        return {
            "status": "healthy",
            "celery_workers": len(celery_status) if celery_status else 0,
            "celery_healthy": celery_healthy,
            "version": "2.0.0"
        }
    except Exception as e:
        logger.error(f"Erreur health check: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "celery_healthy": False
        }


@app.get("/webhook/monday")
async def validate_monday_webhook(request: Request):
    """
    Endpoint GET pour la validation des webhooks Monday.com.
    Monday.com utilise cet endpoint pour vérifier que l'URL est valide.
    """
    try:
        # Monday.com envoie un paramètre 'challenge' pour validation
        challenge = request.query_params.get("challenge")
        
        if challenge:
            logger.info(f"✅ Challenge webhook reçu: {challenge}")
            return JSONResponse(
                content={"challenge": challenge},
                status_code=200,
                headers={"Content-Type": "application/json"}
            )
        else:
            logger.info("ℹ️ Webhook GET sans challenge - endpoint actif")
            return JSONResponse(
                content={"message": "Webhook endpoint actif", "status": "ready"},
                status_code=200,
                headers={"Content-Type": "application/json"}
            )
        
    except Exception as e:
        logger.error(f"❌ Erreur validation webhook: {e}", exc_info=True)
        return JSONResponse(
            content={"error": "Erreur lors de la validation du webhook"},
            status_code=500,
            headers={"Content-Type": "application/json"}
        )
        

@app.post("/webhook/monday")
async def receive_monday_webhook(request: Request):
    """
    Endpoint pour recevoir les webhooks Monday.com.
    """
    try:
        # 🔥 AJOUTEZ CE CODE EN TOUT PREMIER
        # Gestion spéciale pour le challenge de validation Monday.com
        try:
            # Lire le body brut pour inspection
            body_bytes = await request.body()
            body_str = body_bytes.decode('utf-8')
            
            # Vérifier si c'est un simple challenge
            if '"challenge"' in body_str and '"event"' not in body_str:
                import json
                try:
                    payload = json.loads(body_str)
                    if "challenge" in payload and not payload.get("event"):
                        challenge = payload["challenge"]
                        logger.info(f"🎯 Challenge POST reçu: {challenge}")
                        return JSONResponse(content={"challenge": challenge}, status_code=200)
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.warning(f"⚠️ Erreur lecture body: {e}")
        
        # Continuer avec le traitement normal
        payload_raw = await request.json()
        
        # Validation du payload avec le nouveau schéma
        try:
            webhook_payload = WebhookPayload(**payload_raw)
        except Exception as validation_error:
            logger.warning("⚠️ Payload webhook malformé", 
                         error=str(validation_error),
                         payload_keys=list(payload_raw.keys()) if isinstance(payload_raw, dict) else "non-dict")
            
            # Vérifier si c'est quand même un challenge valide
            if "challenge" in payload_raw and not payload_raw.get("event"):
                challenge = payload_raw["challenge"] 
                logger.info(f"✅ Challenge webhook reçu (payload non-standard): {challenge}")
                return JSONResponse(content={"challenge": challenge}, status_code=200)
            
            raise HTTPException(
                status_code=400, 
                detail=f"Format de payload invalide: {str(validation_error)}"
            )
        
        # Vérifier si c'est un challenge de validation Monday.com
        if webhook_payload.challenge and not webhook_payload.event:
            challenge = webhook_payload.challenge
            logger.info(f"✅ Challenge webhook reçu via POST: {challenge}")
            return JSONResponse(content={"challenge": challenge}, status_code=200)
        
        # Vérifier qu'on a bien un événement à traiter
        if not webhook_payload.event:
            logger.warning("⚠️ Webhook reçu sans événement")
            return JSONResponse(
                content={
                    "message": "Webhook reçu mais aucun événement à traiter",
                    "status": "ignored"
                },
                status_code=200
            )
        
        # Extraire les informations de la tâche
        task_info = webhook_payload.extract_task_info()
        if not task_info:
            logger.info("ℹ️ Webhook ignoré - pas de tâche extractable")
            return JSONResponse(
                content={
                    "message": "Webhook reçu mais pas de tâche à traiter",
                    "status": "ignored"
                },
                status_code=200
            )
        
        # Récupérer la signature pour validation sécurisée
        signature = request.headers.get("X-Monday-Signature")
        
        # ✅ PERSISTENCE: Traiter et enregistrer le webhook en temps réel
        persistence_result = await webhook_persistence.process_monday_webhook(
            payload_raw, 
            dict(request.headers), 
            signature
        )
        
        # Logs détaillés du webhook reçu avec persistence
        logger.info("📨 Webhook Monday.com reçu et persisté", 
                   pulse_id=webhook_payload.event.pulseId,
                   board_id=webhook_payload.event.boardId,
                   event_type=webhook_payload.type,
                   task_title=task_info.get("title", "N/A"),
                   task_type=task_info.get("task_type", "N/A"),
                   priority=task_info.get("priority", "N/A"),
                   webhook_id=persistence_result.get("webhook_id"),
                   db_task_id=persistence_result.get("task_id"))
        
        # ✅ CORRECTION: Vérifier si la tâche existe déjà pour éviter la duplication
        if persistence_result.get("task_exists", False):
            logger.info("⚠️ Tâche déjà existante - pas de traitement Celery", 
                       task_id=persistence_result.get("task_id"),
                       pulse_id=webhook_payload.event.pulseId)
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Tâche déjà existante - mise à jour uniquement",
                    "task_id": persistence_result.get("task_id"),
                    "status": "updated",
                    "status_code": 200
                },
                status_code=200
            )
        
        # ✅ CORRECTION: Ne lancer le workflow Celery que pour les nouvelles tâches
        if not persistence_result.get("success") or not persistence_result.get("task_id"):
            logger.warning("❌ Erreur de persistence - pas de lancement Celery")
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Erreur lors de la création de la tâche",
                    "status_code": 400
                },
                status_code=400
            )
        
        # 🚀 Soumettre à RabbitMQ via Celery avec priorité dynamique
        priority_map = {
            "urgent": 9,
            "high": 7, 
            "medium": 5,
            "low": 3
        }
        task_priority = priority_map.get(task_info.get("priority", "medium").lower(), 5)
        
        task = submit_task(
            "ai_agent_background.process_monday_webhook",
            payload_raw,  # Payload original pour compatibilité
            signature,
            priority=task_priority
        )
        
        logger.info("📨 Webhook envoyé à RabbitMQ", 
                   task_id=task.id,
                   webhook_type=webhook_payload.type,
                   queue="webhooks",
                   priority=task_priority,
                   routing_key="webhook.monday")
        
        # Réponse enrichie avec informations extraites et persistence
        return JSONResponse(
            content={
                "message": "Webhook reçu, persiste et traite par RabbitMQ",
                "task_id": task.id,
                "status": "accepted",
                "processing": "rabbitmq_celery",
                "webhook_info": {
                    "pulse_id": webhook_payload.event.pulseId,
                    "task_title": task_info.get("title", ""),
                    "task_type": task_info.get("task_type", ""),
                    "priority": task_info.get("priority", ""),
                    "queue": "webhooks",
                    "priority_level": task_priority
                },
                "persistence_info": {
                    "webhook_id": persistence_result.get("webhook_id"),
                    "db_task_id": persistence_result.get("task_id"),
                    "persistence_success": persistence_result.get("success", False)
                },
                "estimated_processing_time": "2-10 minutes"
            },
            status_code=202
        )
        
    except HTTPException:
        # Re-lever les HTTPExceptions (erreurs de validation, etc.)
        raise
    except Exception as e:
        logger.error("❌ Erreur lors de la reception du webhook", 
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Erreur interne lors du traitement du webhook: {str(e)}"
        )


@app.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """
    Endpoint pour suivre le statut d'une tâche Celery.
    
    Permet de vérifier l'avancement des workflows en temps réel.
    """
    try:
        # Récupérer le résultat de la tâche Celery
        task_result = celery_app.AsyncResult(task_id)
        
        response = {
            "task_id": task_id,
            "status": task_result.status,
            "ready": task_result.ready(),
            "successful": task_result.successful() if task_result.ready() else None,
            "failed": task_result.failed() if task_result.ready() else None,
        }
        
        # Ajouter le résultat si disponible
        if task_result.ready():
            if task_result.successful():
                response["result"] = task_result.result
            elif task_result.failed():
                response["error"] = str(task_result.info)
                response["traceback"] = task_result.traceback
        else:
            # Tâche en cours - essayer de récupérer des infos
            response["info"] = task_result.info
        
        return response
        
    except Exception as e:
        logger.error(f"Erreur recuperation statut tache {task_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la recuperation du statut de la tache"
        )


@app.post("/workflows/execute")
async def execute_workflow_directly(task_request: TaskRequest):
    """
    Endpoint pour lancer un workflow directement (sans passer par Monday.com).
    
    Utile pour les tests et l'execution manuelle.
    """
    try:
        logger.info(f"🎯 Exécution workflow directe: {task_request.title}")
        
        # Soumettre à Celery
        task = submit_task(
            "ai_agent_background.execute_workflow",
            task_request.dict()
        )
        
        return {
            "message": "Workflow soumis à Celery",
            "task_id": task.id,
            "workflow_title": task_request.title,
            "status_url": f"/tasks/{task.id}/status"
        }
        
    except Exception as e:
        logger.error(f"Erreur execution workflow: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de l'exécution du workflow"
        )


@app.get("/costs/{period}")
async def get_costs_summary(period: str = "today"):
    """Recupere le resume des couts IA."""
    try:
        from services.monitoring_service import monitoring_dashboard
        
        valid_periods = ["today", "week", "month", "all"]
        if period not in valid_periods:
            raise HTTPException(
                status_code=400, 
                detail=f"Période invalide. Valides: {valid_periods}"
            )
        
        summary = await monitoring_dashboard.get_costs_summary(period)
        
        if "error" in summary:
            raise HTTPException(status_code=500, detail=summary["error"])
            
        return summary
        
    except Exception as e:
        logger.error(f"❌ Erreur recuperation couts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/celery/status")
async def get_celery_status():
    """
    Endpoint pour verifier le statut des workers Celery.
    """
    try:
        # Inspection des workers
        inspect = celery_app.control.inspect()
        
        # Workers actifs
        active_workers = inspect.ping() or {}
        
        # Tâches actives
        active_tasks = inspect.active() or {}
        
        # Tâches en attente
        reserved_tasks = inspect.reserved() or {}
        
        # Statistiques
        stats = inspect.stats() or {}
        
        total_active_tasks = sum(len(tasks) for tasks in active_tasks.values())
        total_reserved_tasks = sum(len(tasks) for tasks in reserved_tasks.values())
        
        return {
            "workers_count": len(active_workers),
            "workers": list(active_workers.keys()),
            "active_tasks": total_active_tasks,
            "reserved_tasks": total_reserved_tasks,
            "workers_stats": stats,
            "queues": ["webhooks", "workflows", "tests", "ai_generation"]
        }
        
    except Exception as e:
        logger.error(f"Erreur statut Celery: {e}")
        return {
            "error": str(e),
            "workers_count": 0,
            "status": "unavailable"
        }


# Endpoint pour déclencher des tâches de maintenance
@app.post("/admin/cleanup")
async def trigger_cleanup():
    """
    Endpoint admin pour declencher le nettoyage manuel.
    """
    try:
        task = submit_task("ai_agent_background.cleanup_old_tasks")
        
        return {
            "message": "Nettoyage déclenché",
            "task_id": task.id,
            "status_url": f"/tasks/{task.id}/status"
        }
        
    except Exception as e:
        logger.error(f"Erreur déclenchement nettoyage: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erreur lors du déclenchement du nettoyage"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if settings.debug else False,
        log_level=settings.log_level.lower()
    )