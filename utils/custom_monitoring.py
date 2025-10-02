"""Module d'intégration du monitoring custom avec LangGraph."""

import time
from typing import Dict, Any
from functools import wraps

from models.state import GraphState
from services.monitoring_service import MonitoringDashboard
from utils.logger import get_logger
from utils.langsmith_tracing import workflow_tracer

logger = get_logger(__name__)

# Instance globale du dashboard de monitoring
monitoring_dashboard = MonitoringDashboard()


class WorkflowMonitor:
    """Moniteur intégré pour les workflows LangGraph."""
    
    def __init__(self):
        self.active_workflows: Dict[str, Dict] = {}
        
    async def start_monitoring(self, state: GraphState) -> GraphState:
        """Démarre le monitoring pour un workflow."""
        task = state.get("task")
        task_id = task.task_id if task else "unknown"
        workflow_id = f"workflow_{task_id}_{int(time.time())}"
        
        # Ajouter l'ID de workflow à l'état
        state["workflow_id"] = workflow_id
        state["monitoring_start_time"] = time.time()
        state["current_progress"] = 0
        
        # Démarrer le monitoring
        await monitoring_dashboard.start_workflow_monitoring(workflow_id, task)
        
        logger.info("🎯 Monitoring initialisé", workflow_id=workflow_id)
        return state
        
    async def update_progress(self, state: GraphState, step_name: str, 
                            progress: int, logs: list = None) -> GraphState:
        """Met à jour le progrès du workflow."""
        workflow_id = state.get("workflow_id")
        if not workflow_id:
            return state
            
        state["current_progress"] = progress
        
        await monitoring_dashboard.update_workflow_step(
            workflow_id, step_name, progress, logs or []
        )
        
        return state
        
    async def log_ai_interaction(self, state: GraphState, provider: str, 
                               tokens: int, cost: float) -> GraphState:
        """Log une interaction avec l'IA."""
        workflow_id = state.get("workflow_id")
        if not workflow_id:
            return state
            
        await monitoring_dashboard.log_ai_usage(
            workflow_id, provider, tokens, cost
        )
        
        return state
        
    async def finalize_monitoring(self, state: GraphState, 
                                success: bool = True) -> GraphState:
        """Finalise le monitoring du workflow."""
        workflow_id = state.get("workflow_id")
        if not workflow_id:
            return state
            
        await monitoring_dashboard.complete_workflow(
            workflow_id, success, state
        )
        
        total_time = time.time() - state.get("monitoring_start_time", time.time())
        
        logger.info(
            f"{'✅' if success else '❌'} Monitoring terminé",
            workflow_id=workflow_id,
            success=success,
            total_time=f"{total_time:.2f}s"
        )
        
        return state


# Instance globale
workflow_monitor = WorkflowMonitor()


def monitor_step(step_name: str, progress_increment: int = 10):
    """Décorateur pour monitorer automatiquement les étapes LangGraph."""
    def decorator(func):
        @wraps(func)
        async def wrapper(state: GraphState, *args, **kwargs):
            # Récupérer le progrès actuel
            current_progress = state.get("current_progress", 0)
            new_progress = min(current_progress + progress_increment, 100)
            
            # Logs de début
            start_logs = [f"🚀 Début: {step_name}"]
            await workflow_monitor.update_progress(
                state, step_name, current_progress, start_logs
            )
            
            start_time = time.time()
            
            try:
                # Exécuter la fonction
                result = await func(state, *args, **kwargs)
                
                # Calculer durée et logs de succès
                duration = time.time() - start_time
                success_logs = [
                    f"✅ {step_name} terminé avec succès",
                    f"⏱️ Durée: {duration:.2f}s"
                ]
                
                # Extraire des métriques supplémentaires du résultat
                if isinstance(result, dict):
                    if "test_results" in result:
                        tests = result["test_results"]
                        passed = sum(1 for t in tests if getattr(t, 'passed', True))
                        failed = len(tests) - passed
                        success_logs.append(f"🧪 Tests: {passed} ✅ / {failed} ❌")
                        
                    if "code_changes" in result:
                        files_count = len(result["code_changes"])
                        success_logs.append(f"📝 Fichiers modifiés: {files_count}")
                        
                    if "pr_info" in result and result["pr_info"]:
                        success_logs.append(f"🔗 PR créée: {result['pr_info'].get('url', 'N/A')}")
                
                # Mettre à jour le monitoring
                await workflow_monitor.update_progress(
                    result, step_name, new_progress, success_logs
                )
                
                return result
                
            except Exception as e:
                # Logs d'erreur
                duration = time.time() - start_time
                error_logs = [
                    f"❌ Erreur dans {step_name}",
                    f"🔍 Détails: {str(e)}",
                    f"⏱️ Durée avant erreur: {duration:.2f}s"
                ]
                
                await workflow_monitor.update_progress(
                    state, step_name, current_progress, error_logs
                )
                
                logger.error(f"Erreur dans {step_name}", 
                           step=step_name, 
                           error=str(e), 
                           duration=duration)
                raise
                
        return wrapper
    return decorator


# Fonctions utilitaires pour les métriques customisées
async def record_custom_metric(metric_name: str, value: float, 
                             state: GraphState, labels: Dict[str, str] = None):
    """Enregistre une métrique personnalisée."""
    workflow_id = state.get("workflow_id")
    
    all_labels = {"workflow_id": workflow_id} if workflow_id else {}
    if labels:
        all_labels.update(labels)
        
    await monitoring_dashboard.record_metric(metric_name, value, all_labels)


async def log_business_event(event_name: str, state: GraphState, 
                           event_data: Dict[str, Any] = None):
    """Log un événement métier spécifique."""
    workflow_id = state.get("workflow_id")
    task = state.get("task")
    task_id = task.task_id if task else "unknown"
    
    event_data = event_data or {}
    
    logger.info(
        f"📊 Événement métier: {event_name}",
        event=event_name,
        workflow_id=workflow_id,
        task_id=task_id,
        **event_data
    )
    
    # Enregistrer comme métrique
    await monitoring_dashboard.record_metric(
        f"business_event_{event_name}",
        1,
        {
            "workflow_id": workflow_id,
            "task_id": task_id,
            **{k: str(v) for k, v in event_data.items()}
        }
    )


# Métriques spécialisées pour les événements workflow
async def track_ai_usage(state: GraphState, provider: str, 
                        prompt_tokens: int, completion_tokens: int, 
                        estimated_cost: float):
    """Suivi détaillé de l'utilisation IA."""
    total_tokens = prompt_tokens + completion_tokens
    
    await workflow_monitor.log_ai_interaction(
        state, provider, total_tokens, estimated_cost
    )
    
    # Métriques détaillées
    await record_custom_metric("ai_prompt_tokens", prompt_tokens, state, 
                             {"provider": provider})
    await record_custom_metric("ai_completion_tokens", completion_tokens, state, 
                             {"provider": provider})
    await record_custom_metric("ai_cost_usd", estimated_cost, state, 
                             {"provider": provider})
    
    await log_business_event("ai_call_completed", state, {
        "provider": provider,
        "total_tokens": total_tokens,
        "cost_usd": estimated_cost
    })
    
    # Tracer avec LangSmith
    workflow_tracer.trace_business_event(state, "ai_usage", {
        "provider": provider,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost": estimated_cost
    })


async def track_test_execution(state: GraphState, test_type: str, 
                             tests_run: int, tests_passed: int, 
                             execution_time: float):
    """Suivi de l'exécution des tests."""
    tests_failed = tests_run - tests_passed
    success_rate = (tests_passed / tests_run * 100) if tests_run > 0 else 0
    
    await record_custom_metric("tests_executed", tests_run, state, 
                             {"test_type": test_type})
    await record_custom_metric("tests_passed", tests_passed, state, 
                             {"test_type": test_type})
    await record_custom_metric("tests_failed", tests_failed, state, 
                             {"test_type": test_type})
    await record_custom_metric("test_execution_time", execution_time, state, 
                             {"test_type": test_type})
    await record_custom_metric("test_success_rate", success_rate, state, 
                             {"test_type": test_type})
    
    await log_business_event("tests_completed", state, {
        "test_type": test_type,
        "tests_run": tests_run,
        "tests_passed": tests_passed,
        "success_rate": f"{success_rate:.1f}%",
        "execution_time": f"{execution_time:.2f}s"
    })


async def track_git_operation(state: GraphState, operation: str, 
                            success: bool, files_changed: int = 0):
    """Suivi des opérations Git."""
    await record_custom_metric("git_operation", 1, state, {
        "operation": operation,
        "success": str(success)
    })
    
    if files_changed > 0:
        await record_custom_metric("files_changed", files_changed, state, 
                                 {"operation": operation})
    
    await log_business_event("git_operation_completed", state, {
        "operation": operation,
        "success": success,
        "files_changed": files_changed
    }) 