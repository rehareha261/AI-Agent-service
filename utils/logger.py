"""Module de logging structuré avec support Rich et couleurs."""

import logging
import structlog
from rich.console import Console
from rich.logging import RichHandler
from typing import Any, Dict


def configure_logging(debug: bool = False, log_level: str = "INFO") -> None:
    """
    Configure le système de logging avec structlog et Rich.
    
    Args:
        debug: Mode debug activé
        log_level: Niveau de log (DEBUG, INFO, WARNING, ERROR)
    """
    # Configuration du niveau de log
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configuration de Rich pour les logs colorés
    console = Console(force_terminal=True)
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_level=True,
        show_path=debug,
        markup=True,
        rich_tracebacks=True
    )
    
    # Configuration du logger standard
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[rich_handler]
    )
    
    # Configuration de structlog
    structlog.configure(
        processors=[
            # Traitement des métadonnées
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            
            # Formatage conditionnel
            structlog.dev.ConsoleRenderer(colors=True) if debug 
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Récupère un logger structuré pour un module.
    
    Args:
        name: Nom du module (généralement __name__)
        
    Returns:
        Logger structuré configuré
    """
    # Configurer le logging si pas encore fait
    if not hasattr(get_logger, '_configured'):
        configure_logging()
        get_logger._configured = True
    
    return structlog.get_logger(name)


class LoggerMixin:
    """Mixin pour ajouter facilement un logger à une classe."""
    
    @property
    def logger(self) -> structlog.BoundLogger:
        """Récupère le logger pour cette classe."""
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__module__)
        return self._logger


# Logger global pour l'application
app_logger = get_logger("ai-automation-agent")


def log_workflow_step(step_name: str, task_id: str, **kwargs) -> None:
    """
    Log une étape de workflow avec contexte.
    
    Args:
        step_name: Nom de l'étape
        task_id: ID de la tâche
        **kwargs: Métadonnées additionnelles
    """
    app_logger.info(
        f"🔄 Étape: {step_name}",
        step=step_name,
        task_id=task_id,
        **kwargs
    )


def log_error(error: Exception, context: Dict[str, Any] = None) -> None:
    """
    Log une erreur avec contexte détaillé.
    
    Args:
        error: Exception à logger
        context: Contexte additionnel
    """
    context = context or {}
    
    app_logger.error(
        f"❌ Erreur: {str(error)}",
        error_type=type(error).__name__,
        error_message=str(error),
        **context,
        exc_info=True
    )


def log_success(message: str, **kwargs) -> None:
    """
    Log un succès avec métadonnées.
    
    Args:
        message: Message de succès
        **kwargs: Métadonnées additionnelles
    """
    app_logger.info(f"✅ {message}", **kwargs)


def log_warning(message: str, **kwargs) -> None:
    """
    Log un avertissement avec métadonnées.
    
    Args:
        message: Message d'avertissement
        **kwargs: Métadonnées additionnelles
    """
    app_logger.warning(f"⚠️ {message}", **kwargs) 