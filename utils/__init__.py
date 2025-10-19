# -*- coding: utf-8 -*-
"""Utilitaires de l'application."""

# ✅ CORRECTION: Imports supprimés pour éviter l'import circulaire
# Les modules peuvent importer directement: from utils.logger import get_logger
# Au lieu de: from utils import get_logger

__all__ = [
    "get_logger", 
    "configure_logging",
    "validate_webhook_signature", 
    "sanitize_branch_name",
    "get_working_directory",
    "validate_working_directory", 
    "ensure_working_directory",
    "ensure_state_structure",
    "add_ai_message",
    "add_error_log",
    "ensure_state_integrity",
    "with_persistence",
    "log_code_generation_decorator",
    "extract_github_url_from_description",
    "enrich_task_with_description_info",
    "MonitoringDashboard",
    "PerformanceMonitor"
] 