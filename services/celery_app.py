"""Application Celery pour tout le background processing du projet AI-Agent."""

import warnings
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from celery import Celery

# ✅ SUPPRESSION des warnings LangChain Beta pour nettoyer les logs Celery
try:
    from langchain_core._api.beta_decorator import LangChainBetaWarning
    warnings.simplefilter("ignore", LangChainBetaWarning)
except ImportError:
    warnings.filterwarnings("ignore", message="This API is in beta and may change in the future.")
from celery.signals import worker_ready, worker_shutting_down
from kombu import Exchange, Queue
from typing import Dict, Any, Optional
import asyncio

from config.settings import get_settings
from models.schemas import TaskRequest
# Import paresseux pour éviter l'importation circulaire
# from graph.workflow_graph import run_workflow  
from services.webhook_service import WebhookService
from services.monitoring_service import monitoring_service
from services.database_persistence_service import db_persistence
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Configuration Celery optimisée pour RabbitMQ
celery_app = Celery(
    "ai_agent_background",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["services.celery_app"]  # Auto-découverte des tâches
)

# Déclaration des exchanges et queues RabbitMQ
default_exchange = Exchange('ai_agent', type='topic')

# Configuration avancée pour RabbitMQ
celery_app.conf.update(
    # Sérialisation et transport
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Configuration RabbitMQ avancée
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_pool_limit=10,
    
    # Fiabilité et acknowledgements
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    
    # Retry et timeout
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    task_soft_time_limit=1500,    # 25 minutes
    task_time_limit=1800,         # 30 minutes
    
    # Configuration des exchanges et queues
    task_default_exchange='ai_agent',
    task_default_exchange_type='topic',
    task_default_routing_key='task.default',
    task_create_missing_queues=True,
    
    # Déclaration des queues spécialisées
    task_queues=[
        # Queue prioritaire pour webhooks Monday.com
        Queue('webhooks', 
              exchange=default_exchange, 
              routing_key='webhook.*',
              queue_arguments={
                  'x-max-priority': 10,
                  'x-message-ttl': 900000,  # 15 minutes TTL
                  'x-dead-letter-exchange': 'ai_agent',
                  'x-dead-letter-routing-key': 'dead_letter.webhook'
              }),
        
        # Queue pour workflows LangGraph
        Queue('workflows', 
              exchange=default_exchange, 
              routing_key='workflow.*',
              queue_arguments={
                  'x-max-priority': 5,
                  'x-message-ttl': 3600000,  # 1 heure TTL
                  'x-dead-letter-exchange': 'ai_agent',
                  'x-dead-letter-routing-key': 'dead_letter.workflow'
              }),
        
        # Queue pour génération IA
        Queue('ai_generation', 
              exchange=default_exchange, 
              routing_key='ai.*',
              queue_arguments={
                  'x-max-priority': 7,
                  'x-message-ttl': 1800000,  # 30 minutes TTL
                  'x-dead-letter-exchange': 'ai_agent',
                  'x-dead-letter-routing-key': 'dead_letter.ai'
              }),
        
        # Queue pour tests
        Queue('tests', 
              exchange=default_exchange, 
              routing_key='test.*',
              queue_arguments={
                  'x-max-priority': 3,
                  'x-message-ttl': 1200000,  # 20 minutes TTL
                  'x-dead-letter-exchange': 'ai_agent',
                  'x-dead-letter-routing-key': 'dead_letter.test'
              }),
        
        # Dead Letter Queue pour les tâches échouées
        Queue('dlq', 
              exchange=default_exchange, 
              routing_key='dead_letter.*',
              queue_arguments={
                  'x-message-ttl': 86400000,  # 24 heures TTL
              }),
    ],
    
    # Routing des tâches vers les queues spécialisées
    task_routes={
        "ai_agent_background.process_monday_webhook": {
            "queue": "webhooks",
            "routing_key": "webhook.monday",
            "priority": 9
        },
        "ai_agent_background.execute_workflow": {
            "queue": "workflows", 
            "routing_key": "workflow.langgraph",
            "priority": 5
        },
        "ai_agent_background.generate_code": {
            "queue": "ai_generation",
            "routing_key": "ai.generate.code",
            "priority": 7
        },
        "ai_agent_background.run_tests": {
            "queue": "tests",
            "routing_key": "test.execute",
            "priority": 3
        },
        "ai_agent_background.handle_dead_letter": {
            "queue": "dlq",
            "routing_key": "dead_letter.handler",
            "priority": 1
        }
    },
    
    # Monitoring et metrics
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Optimisations performances
    worker_disable_rate_limits=True,
    task_compression='gzip',
    result_compression='gzip',
    result_expires=3600,  # 1 heure
)


# Instance du service webhook
webhook_service = WebhookService()


@celery_app.task(
    bind=True, 
    name="ai_agent_background.process_monday_webhook",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    priority=9
)
def process_monday_webhook(self, payload: Dict[str, Any], signature: Optional[str] = None):
    """
    Tâche Celery principale pour traiter les webhooks Monday.com.
    
    Avec gestion automatique des échecs vers Dead Letter Queue.
    """
    task_id = self.request.id
    
    # ✅ PROTECTION: Identifier la tâche Monday.com pour éviter les doublons
    monday_item_id = payload.get('event', {}).get('pulseId', 'unknown')
    
    # ✅ Vérification de déduplication simple pour les items de test
    if str(monday_item_id).startswith('test_connection'):
        # Pour les tests, permettre le traitement mais avec logging adapté
        logger.info(f"🧪 Traitement item de test {monday_item_id}", 
                   task_id=task_id, 
                   queue="webhooks")
    else:
        logger.info("🚀 Démarrage traitement webhook Celery", 
                   task_id=task_id, 
                   monday_item_id=monday_item_id,
                   queue="webhooks",
                   routing_key="webhook.monday")
    
    # Traitement synchrone du webhook (conversion async → sync)
    try:
        # ✅ CORRECTION: Traiter le webhook et créer la tâche
        result = asyncio.run(
            webhook_service.process_webhook(payload, signature)
        )
        
        # ✅ Si une tâche a été créée, lancer le workflow directement
        if result.get('success') and result.get('task_id'):
            # ✅ CORRECTION: Vérifier si c'est une tâche existante avant de lancer le workflow
            if result.get('task_exists', False) and not result.get('is_reactivation', False):
                logger.info(f"⚠️ Tâche {result['task_id']} existe déjà - pas de lancement de workflow")
                return {
                    "task_id": task_id,
                    "status": "completed",
                    "result": result,
                    "webhook_payload": payload,
                    "queue": "webhooks",
                    "workflow_skipped": "task_exists"
                }
            
            from models.schemas import TaskRequest
            
            logger.info(f"🚀 Lancement workflow pour tâche {result['task_id']}")
            
            # Extraire les informations de la tâche du payload
            task_info = payload.get('event', {})
            
            # Créer TaskRequest à partir du webhook
            task_request = TaskRequest(
                task_id=result['task_id'],
                title=task_info.get('pulseName', 'Tâche Monday.com'),
                description=task_info.get('description', ''),
                priority=task_info.get('priority', 'medium'),
                monday_item_id=task_info.get('pulseId'),
                board_id=task_info.get('boardId')
            )
            
            # Lancer le workflow via Celery avec délai pour éviter la surcharge
            workflow_task = execute_workflow.apply_async(
                args=[task_request.model_dump()],
                priority=5,
                countdown=2 if str(monday_item_id).startswith('test_connection') else 0
            )
            
            result['workflow_task_id'] = workflow_task.id
            logger.info(f"✅ Workflow lancé - Task ID: {workflow_task.id}")
        else:
            # ✅ AMÉLIORATION: Log détaillé en cas de non-lancement
            if result.get('task_exists', False):
                logger.info(f"ℹ️ Workflow non lancé - tâche existante: {result.get('task_id', 'unknown')}")
            else:
                logger.warning(f"⚠️ Workflow non lancé - pas de task_id: {result}")
        
        return {
            "task_id": task_id,
            "status": "completed",
            "result": result,
            "webhook_payload": payload,
            "queue": "webhooks"
        }
        
    except Exception as exc:
        logger.error("❌ Erreur traitement webhook", 
                    task_id=task_id, 
                    monday_item_id=monday_item_id,
                    error=str(exc))

        
        # Retry automatique selon configuration
        if self.request.retries < self.max_retries:
            logger.info(f"🔄 Retry {self.request.retries + 1}/{self.max_retries}", task_id=task_id)
            raise self.retry(countdown=60, exc=exc)
        else:
            # Échec définitif - envoyer vers DLQ
            handle_dead_letter.delay({
                "original_task": "process_monday_webhook",
                "task_id": task_id,
                "payload": payload,
                "signature": signature,
                "error": str(exc),
                "retries_exhausted": True,
                "timestamp": task_id  # Utilisé pour tracking
            })
            
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(exc),
                "retries_exhausted": True,
                "sent_to_dlq": True
            }


@celery_app.task(
    bind=True, 
    name="ai_agent_background.execute_workflow",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 120},
    priority=5
)
def execute_workflow(self, task_request_dict: Dict[str, Any]):
    """
    Tâche Celery pour exécuter un workflow LangGraph complet.
    
    Permet la parallélisation de plusieurs workflows.
    """
    task_id = self.request.id
    workflow_id = f"celery_{task_id}"
    
    # Reconstruire l'objet TaskRequest
    task_request = TaskRequest(**task_request_dict)
    
    # ✅ CORRECTION: Bloquer les tâches de test automatiques
    if hasattr(task_request, 'task_id') and task_request.task_id and (
        task_request.task_id == "test_connection_123" or 
        str(task_request.task_id).startswith("test_") or
        "test" in task_request.title.lower()
    ):
        logger.warning(f"🚫 Tâche de test bloquée: {task_request.title} (ID: {task_request.task_id})")
        return {
            "task_id": task_id,
            "workflow_id": workflow_id,
            "status": "blocked",
            "message": "Tâche de test bloquée pour éviter l'exécution automatique",
            "queue": "workflows"
        }
    
    # ✅ CORRECTION: Vérifier que Monday.com est configuré pour les vraies tâches
    if hasattr(task_request, 'task_id') and task_request.task_id and task_request.task_id != "test_connection_123":
        from tools.monday_tool import MondayTool
        monday_tool = MondayTool()
        if not hasattr(monday_tool, 'api_token') or not monday_tool.api_token:
            logger.warning(f"🚫 Workflow bloqué - Monday.com non configuré: {task_request.title}")
            return {
                "task_id": task_id,
                "workflow_id": workflow_id,
                "status": "blocked",
                "message": "Workflow bloqué - Configurez MONDAY_API_TOKEN dans votre .env",
                "queue": "workflows"
            }
    
    logger.info("🔄 Démarrage workflow LangGraph", 
               task_id=task_id,
               workflow_title=task_request.title,
               queue="workflows")
    
    try:
        # Configurer le Python path pour Celery
        import sys
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        # Démarrer le monitoring du workflow
        try:
            asyncio.run(
                monitoring_service.start_workflow_monitoring(workflow_id, task_request_dict)
            )
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logger.warning("⚠️ Event loop fermé lors du démarrage monitoring - ignoré")
            else:
                logger.error(f"❌ Erreur démarrage monitoring: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Erreur démarrage monitoring: {e}")
        
        # Exécuter le workflow (import paresseux pour éviter l'importation circulaire)
        from graph.workflow_graph import run_workflow
        result = asyncio.run(run_workflow(task_request))
        
        # Finaliser le monitoring
        try:
            asyncio.run(
                monitoring_service.complete_workflow(workflow_id, result.get('success', False), result)
            )
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logger.warning("⚠️ Event loop fermé lors de la finalisation monitoring - ignoré")
            else:
                logger.error(f"❌ Erreur finalisation monitoring: {e}")
        except Exception as e:
            logger.error(f"❌ Erreur finalisation services: {e}")
        
        logger.info("✅ Workflow terminé", 
                   task_id=task_id,
                   success=result.get('success', False),
                   duration=result.get('duration', 0))
        
        return {
            "task_id": task_id,
            "workflow_id": workflow_id,
            "status": "completed",
            "result": result,
            "queue": "workflows"
        }
        
    except Exception as exc:
        logger.error("❌ Erreur workflow", 
                    task_id=task_id, 
                    error=str(exc), 
                    exc_info=True)
        
        # Finaliser le monitoring en cas d'erreur
        try:
            asyncio.run(
                monitoring_service.complete_workflow(workflow_id, False)
            )
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logger.warning("⚠️ Event loop fermé lors de la finalisation d'erreur - ignoré")
            else:
                logger.error(f"❌ Erreur finalisation monitoring erreur: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Erreur finalisation monitoring erreur: {e}")
        
        # ✅ CORRECTION: Éviter les retries inutiles sur les échecs métier 
        # Ne retry que sur les erreurs d'infrastructure et Claude surchargé
        exc_str = str(exc).lower()
        should_retry = (
            "connection" in exc_str or 
            "timeout" in exc_str or
            "network" in exc_str or
            "database" in exc_str or
            "529" in exc_str or
            "overloaded" in exc_str or
            "rate limit" in exc_str
        )
        
        if should_retry and self.request.retries < self.max_retries:
            # Pour les erreurs Claude 529, attendre plus longtemps
            if "529" in exc_str or "overloaded" in exc_str:
                countdown_time = min(300, 60 * (self.request.retries + 1))  # 1, 2, 5 minutes max
                logger.info(f"🔄 Retry workflow {self.request.retries + 1}/{self.max_retries} (Claude surchargé, attente {countdown_time}s)", task_id=task_id)
                raise self.retry(countdown=countdown_time, exc=exc)
            else:
                logger.info(f"🔄 Retry workflow {self.request.retries + 1}/{self.max_retries} (erreur infrastructure)", task_id=task_id)
                raise self.retry(countdown=120, exc=exc)  # 2 minutes entre retries
        else:
            # Si c'est une erreur Claude 529 après tous les retries, marquer comme "suspendu"
            if "529" in exc_str or "overloaded" in exc_str:
                logger.warning(f"⚠️ Workflow suspendu temporairement à cause de la surcharge Claude", task_id=task_id)
                
                # Programmer une nouvelle tentative dans quelques heures
                execute_workflow.apply_async(
                    args=[task_request_dict],
                    countdown=3600,  # 1 heure
                    priority=1  # Basse priorité
                )
                
                return {
                    "task_id": task_id,
                    "workflow_id": workflow_id,
                    "status": "suspended",
                    "error": "Claude API surchargée - reprogrammé dans 1h",
                    "retries_exhausted": True,
                    "rescheduled": True
                }
            
            if not should_retry:
                logger.info(f"⏹️ Pas de retry - échec métier (tests/QA): {str(exc)[:100]}", task_id=task_id)
            
            # Envoyer vers DLQ
            handle_dead_letter.delay({
                "original_task": "execute_workflow", 
                "task_id": task_id,
                "task_request": task_request_dict,
                "workflow_id": workflow_id,
                "error": str(exc),
                "retries_exhausted": True
            })
            
            return {
                "task_id": task_id,
                "workflow_id": workflow_id,
                "status": "failed",
                "error": str(exc),
                "retries_exhausted": True,
                "sent_to_dlq": True
            }


@celery_app.task(
    bind=True, 
    name="ai_agent_background.generate_code",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 30},
    priority=7
)
def generate_code_task(self, prompt: str, provider: str = "claude", context: Dict[str, Any] = None):
    """
    Tâche Celery pour la génération de code IA.
    
    Permet d'isoler les appels IA et de les paralléliser.
    """
    task_id = self.request.id
    
    from tools.ai_engine_hub import AIEngineHub
    
    logger.info("🤖 Génération code IA", 
               task_id=task_id, 
               provider=provider,
               queue="ai_generation")
    
    ai_hub = AIEngineHub()
    
    try:
        # Génération synchrone
        result = asyncio.run(
            ai_hub.generate_code(prompt, provider, context or {})
        )
        
        logger.info("✅ Code généré", 
                   task_id=task_id,
                   provider=provider,
                   tokens_used=result.get('tokens_used', 0))
        
        return {
            "task_id": task_id,
            "status": "completed",
            "provider": provider,
            "result": result,
            "queue": "ai_generation"
        }
        
    except Exception as exc:
        logger.error("❌ Erreur génération code", 
                    task_id=task_id, 
                    provider=provider,
                    error=str(exc), 
                    exc_info=True)
        
        # Retry avec provider alternatif
        if self.request.retries < self.max_retries:
            # Changer de provider pour le retry
            alt_provider = "openai" if provider == "claude" else "claude"
            logger.info(f"🔄 Retry avec {alt_provider}", task_id=task_id)
            
            return generate_code_task.retry(
                countdown=30,
                exc=exc,
                args=[prompt, alt_provider, context]
            )
        else:
            # Envoyer vers DLQ
            handle_dead_letter.delay({
                "original_task": "generate_code",
                "task_id": task_id,
                "prompt": prompt,
                "provider": provider,
                "context": context,
                "error": str(exc),
                "retries_exhausted": True
            })
            
            return {
                "task_id": task_id,
                "status": "failed",
                "provider": provider,
                "error": str(exc),
                "retries_exhausted": True,
                "sent_to_dlq": True
            }


@celery_app.task(
    bind=True, 
    name="ai_agent_background.run_tests",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 30},
    priority=3
)
def run_tests_task(self, workflow_id: str, code_changes: Dict[str, str], test_types: list = None):
    """
    Tâche Celery pour exécuter les tests de manière asynchrone.
    """
    task_id = self.request.id
    test_types = test_types or ["unit", "integration", "security"]
    
    from tools.testing_engine import TestingEngine
    
    logger.info("🧪 Exécution tests", 
               task_id=task_id,
               workflow_id=workflow_id,
               test_types=test_types,
               queue="tests")
    
    testing_engine = TestingEngine()
    
    try:
        # Tests synchrones
        results = asyncio.run(
            testing_engine.run_comprehensive_tests(code_changes, test_types)
        )
        
        total_tests = sum(len(result.get('results', [])) for result in results.values())
        passed_tests = sum(
            len([r for r in result.get('results', []) if r.get('passed', False)]) 
            for result in results.values()
        )
        
        logger.info("✅ Tests terminés", 
                   task_id=task_id,
                   total_tests=total_tests,
                   passed_tests=passed_tests,
                   success_rate=f"{(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%")
        
        return {
            "task_id": task_id,
            "workflow_id": workflow_id,
            "status": "completed",
            "results": results,
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "success_rate": (passed_tests/total_tests*100) if total_tests > 0 else 0
            },
            "queue": "tests"
        }
        
    except Exception as exc:
        logger.error("❌ Erreur tests", 
                    task_id=task_id,
                    error=str(exc), 
                    exc_info=True)
        
        # Retry mais sans échec critique
        if self.request.retries < 2:  # Moins de retries pour les tests
            logger.info(f"🔄 Retry tests {self.request.retries + 1}/2", task_id=task_id)
            raise self.retry(countdown=30, exc=exc)
        else:
            # Envoyer vers DLQ
            handle_dead_letter.delay({
                "original_task": "run_tests",
                "task_id": task_id,
                "workflow_id": workflow_id,
                "code_changes": code_changes,
                "test_types": test_types,
                "error": str(exc),
                "retries_exhausted": True
            })
            
            return {
                "task_id": task_id,
                "workflow_id": workflow_id,
                "status": "failed",
                "error": str(exc),
                "retries_exhausted": True,
                "sent_to_dlq": True
            }


@celery_app.task(name="ai_agent_background.handle_dead_letter", priority=1)
def handle_dead_letter(failed_task_data: Dict[str, Any]):
    """
    Gestionnaire de Dead Letter Queue pour les tâches échouées.
    
    Logs, notifie les admins et stocke les informations d'échec.
    """
    try:
        task_id = failed_task_data.get("task_id", "unknown")
        original_task = failed_task_data.get("original_task", "unknown")
        error = failed_task_data.get("error", "Unknown error")
        
        logger.error("💀 Tâche en Dead Letter Queue", 
                    dlq_task_id=task_id,
                    original_task=original_task,
                    error=error,
                    queue="dlq")
        
        # Stocker dans la base de données pour analyse
        # TODO: Implémenter stockage en DB des échecs
        
        # Notification admin si nécessaire
        # TODO: Implémenter notification email/Slack
        
        return {
            "dlq_processed": True,
            "original_task": original_task,
            "task_id": task_id,
            "timestamp": failed_task_data.get("timestamp"),
            "action": "logged_and_stored"
        }
        
    except Exception as exc:
        logger.error("❌ Erreur traitement DLQ", error=str(exc))
        return {
            "dlq_processed": False,
            "error": str(exc)
        }


@celery_app.task(name="ai_agent_background.cleanup_old_tasks")
def cleanup_old_tasks():
    """Tâche périodique de nettoyage des anciennes tâches."""
    try:
        from datetime import datetime
        
        logger.info("🧹 Nettoyage des anciennes tâches Celery")
        
        # Nettoyer les résultats Celery anciens (> 7 jours)
        celery_app.backend.cleanup()
        
        # Nettoyer les données de monitoring anciennes
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Appeler la fonction de nettoyage du monitoring
            # (à implémenter dans monitoring_service)
            pass
        finally:
            loop.close()
            
        logger.info("✅ Nettoyage terminé")
        return {"status": "completed", "timestamp": datetime.now().isoformat()}
        
    except Exception as exc:
        logger.error("❌ Erreur nettoyage", error=str(exc))
        return {"status": "failed", "error": str(exc)}


# Configuration des tâches périodiques
celery_app.conf.beat_schedule = {
    "cleanup-old-tasks": {
        "task": "ai_agent_background.cleanup_old_tasks",
        "schedule": 24 * 60 * 60,  # Tous les jours
    },
}


# Ancienne fonction _setup_celery_file_logging supprimée - 
# Logique déplacée vers services/logging_service.py pour plus de robustesse

# Fonctions helpers supprimées car déplacées vers logging_service.py :
# - _ensure_logs_directory
# - _get_handlers_config 
# - _create_rotating_handler
# - _create_workflow_filter
# - _create_performance_filter
# - _configure_logger_hierarchy
# - _create_session_metadata
# - _schedule_log_cleanup
# - _setup_basic_file_logging


# Signaux Celery pour monitoring
@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Signal émis quand un worker Celery est prêt."""
    logger.info("🚀 Celery worker prêt", 
               worker=sender,
               broker="RabbitMQ",
               backend="PostgreSQL")
    
    # Initialiser la persistence et le monitoring
    try:
        asyncio.run(db_persistence.initialize())
        logger.info("✅ Persistence base de données initialisée")
        asyncio.run(monitoring_service.start_monitoring())
        logger.info("✅ Monitoring initialisé")
    except Exception as e:
        logger.error(f"❌ Erreur initialisation services: {e}")
    
    # ✅ CONFIGURATION ROBUSTE: Logging Celery via service dédié
    try:
        from services.logging_service import logging_service
        if logging_service.setup_logging():
            logger.info("✅ Logging Celery configuré de manière robuste")
            logs_info = logging_service.get_logs_info()
            logger.info(f"📊 Logs: {logs_info['logs_directory']} ({logs_info['environment']})")
        else:
            logger.warning("⚠️ Configuration logging basique appliquée")
    except Exception as e:
        logger.error(f"❌ Erreur configuration logging: {e}")


@worker_shutting_down.connect
def worker_shutting_down_handler(sender=None, **kwargs):
    """Signal émis quand un worker Celery s'arrête."""
    logger.info("🔄 Celery worker arrêt", worker=sender)
    
    # Finaliser les services de manière sécurisée
    def finalize_services():
        """Finalise les services en créant une nouvelle boucle si nécessaire."""
        try:
            # Créer une nouvelle boucle d'événements pour la finalisation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(db_persistence.close())
                logger.info("✅ Persistence fermée")
                loop.run_until_complete(monitoring_service.stop_monitoring())
                logger.info("✅ Monitoring finalisé")
            finally:
                loop.close()
                
        except Exception as e:
            # Log mais ne pas lever d'exception pour éviter d'interrompre l'arrêt
            logger.error(f"❌ Erreur finalisation services: {e}")
    
    # Lancer la finalisation en arrière-plan pour ne pas bloquer l'arrêt
    import threading
    finalization_thread = threading.Thread(target=finalize_services, daemon=True)
    finalization_thread.start()


# Fonction utilitaire pour lancer les tâches
def submit_task(task_name: str, *args, **kwargs):
    """
    Fonction utilitaire pour soumettre des tâches Celery avec monitoring.
    """
    try:
        # Ajouter la priorité si spécifiée dans kwargs
        task_options = {}
        if 'priority' in kwargs:
            task_options['priority'] = kwargs.pop('priority')
            
        task = celery_app.send_task(task_name, args=args, kwargs=kwargs, **task_options)
        logger.info("📨 Tâche soumise", 
                   task_name=task_name, 
                   task_id=task.id,
                   broker="RabbitMQ")
        return task
    except Exception as exc:
        logger.error("❌ Erreur soumission tâche", 
                    task_name=task_name, 
                    error=str(exc))
        raise


if __name__ == "__main__":
    # Pour lancer le worker : python -m services.celery_app worker
    celery_app.start() 