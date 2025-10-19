"""Définition de l'état pour LangGraph."""

from typing import Dict, Any, Optional, List
from typing_extensions import Annotated, TypedDict
from datetime import datetime

from .schemas import TaskRequest, WorkflowStatus, add_to_list, merge_results


class GraphState(TypedDict, total=False):
    """État principal pour LangGraph - compatibilité avec WorkflowState."""
    workflow_id: str
    status: WorkflowStatus  
    current_node: Optional[str]
    completed_nodes: Annotated[List[str], add_to_list]
    task: Optional[TaskRequest]
    results: Annotated[Dict[str, Any], merge_results]
    error: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    langsmith_session: Optional[str]  # Session LangSmith pour tracing
    
    # ✅ CORRECTION: Ajout des champs de persistence manquants
    # Ces champs sont des int et doivent le rester (ce sont des foreign keys DB)
    db_task_id: Optional[int]  # ID de la tâche en base de données (tasks_id)
    db_run_id: Optional[int]   # ID du run en base de données (tasks_runs_id)
    db_step_id: Optional[int]  # ID du step en cours (run_steps_id)
    current_step_id: Optional[int]  # Alias pour db_step_id (pour compatibilité)


# Alias pour compatibilité
WorkflowState = GraphState 