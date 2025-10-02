"""Configuration des optimisations de performance pour l'Agent AI."""

import os
from typing import Dict, Any

class PerformanceConfig:
    """Configuration des optimisations de performance."""
    
    # ✅ TIMEOUTS OPTIMISÉS (en secondes)
    API_REQUEST_TIMEOUT = 30        # Réduit de 120 à 30s
    TEST_EXECUTION_TIMEOUT = 60     # Réduit de 180 à 60s
    AI_RESPONSE_TIMEOUT = 45        # Réduit de 120 à 45s
    GIT_OPERATION_TIMEOUT = 30      # Nouveau timeout pour Git
    QA_ANALYSIS_TIMEOUT = 45        # Nouveau timeout pour QA
    
    # ✅ LIMITATIONS POUR RÉDUIRE LA CHARGE
    MAX_FILES_TO_ANALYZE = 10       # Augmenté de 5 à 10 pour plus de flexibilité
    MAX_TEST_FILES_TO_RUN = 20      # Limiter le nombre de tests
    MAX_QA_TOOLS_PARALLEL = 3       # Limiter les outils QA en parallèle
    MAX_AI_CALLS_PER_NODE = 3       # Limiter les appels IA par nœud
    
    # ✅ OPTIMISATIONS CACHING
    ENABLE_AI_RESPONSE_CACHE = True
    CACHE_DURATION_MINUTES = 30
    ENABLE_QA_RESULT_CACHE = True
    ENABLE_TEST_RESULT_CACHE = True
    
    # ✅ OPTIMISATIONS WORKFLOW
    SKIP_EXPENSIVE_QA_TOOLS = ["mypy", "complexity-analysis"]  # Outils lents optionnels
    PRIORITIZE_FAST_TESTS = True
    ENABLE_EARLY_SUCCESS = True     # Arrêter dès que possible si succès
    PARALLEL_OPERATIONS = True      # Paralléliser quand possible
    
    # ✅ OPTIMISATIONS RESSOURCES
    MAX_MEMORY_MB = 512             # Limite mémoire pour les opérations
    MAX_CPU_CORES = 2               # Limite CPU pour éviter la surcharge
    CLEANUP_TEMP_FILES = True       # Nettoyer les fichiers temporaires
    
    @classmethod
    def get_optimized_timeout(cls, operation_type: str) -> int:
        """Retourne un timeout optimisé pour un type d'opération."""
        timeouts = {
            "api_request": cls.API_REQUEST_TIMEOUT,
            "test_execution": cls.TEST_EXECUTION_TIMEOUT,
            "ai_response": cls.AI_RESPONSE_TIMEOUT,
            "git_operation": cls.GIT_OPERATION_TIMEOUT,
            "qa_analysis": cls.QA_ANALYSIS_TIMEOUT,
            "file_operation": 15,  # Opérations fichier rapides
            "database_operation": 10  # Opérations DB rapides
        }
        return timeouts.get(operation_type, 30)  # Default 30s
    
    @classmethod
    def should_skip_operation(cls, operation_name: str, estimated_duration: float = 0) -> bool:
        """Détermine si une opération doit être skippée pour les performances."""
        
        # Skip opérations très lentes
        if estimated_duration > 60:  # Plus de 1 minute
            return True
            
        # Skip outils QA lents si configuré
        if operation_name in cls.SKIP_EXPENSIVE_QA_TOOLS:
            return True
            
        # Skip si trop de fichiers à analyser
        if "analyze" in operation_name.lower() and "files" in operation_name.lower():
            return False  # Garder l'analyse de fichiers
            
        return False
    
    @classmethod
    def get_parallel_limit(cls, operation_type: str) -> int:
        """Retourne la limite de parallélisation pour un type d'opération."""
        limits = {
            "qa_tools": cls.MAX_QA_TOOLS_PARALLEL,
            "ai_calls": cls.MAX_AI_CALLS_PER_NODE,
            "test_files": cls.MAX_TEST_FILES_TO_RUN,
            "file_analysis": cls.MAX_FILES_TO_ANALYZE
        }
        return limits.get(operation_type, 5)  # Default 5
    
    @classmethod
    def is_caching_enabled(cls, cache_type: str) -> bool:
        """Vérifie si le caching est activé pour un type donné."""
        caching = {
            "ai_response": cls.ENABLE_AI_RESPONSE_CACHE,
            "qa_result": cls.ENABLE_QA_RESULT_CACHE,
            "test_result": cls.ENABLE_TEST_RESULT_CACHE
        }
        return caching.get(cache_type, False)
    
    @classmethod
    def get_performance_profile(cls) -> Dict[str, Any]:
        """Retourne le profil de performance actuel."""
        return {
            "mode": "optimized",
            "timeouts": {
                "api": cls.API_REQUEST_TIMEOUT,
                "tests": cls.TEST_EXECUTION_TIMEOUT,
                "ai": cls.AI_RESPONSE_TIMEOUT
            },
            "limits": {
                "max_files": cls.MAX_FILES_TO_ANALYZE,
                "max_tests": cls.MAX_TEST_FILES_TO_RUN,
                "max_qa_parallel": cls.MAX_QA_TOOLS_PARALLEL
            },
            "optimizations": {
                "caching": cls.ENABLE_AI_RESPONSE_CACHE,
                "parallel": cls.PARALLEL_OPERATIONS,
                "early_success": cls.ENABLE_EARLY_SUCCESS,
                "skip_expensive": len(cls.SKIP_EXPENSIVE_QA_TOOLS) > 0
            },
            "resources": {
                "max_memory_mb": cls.MAX_MEMORY_MB,
                "max_cpu_cores": cls.MAX_CPU_CORES,
                "cleanup_temp": cls.CLEANUP_TEMP_FILES
            }
        }

# Configuration globale d'optimisation
PERFORMANCE_MODE = os.getenv("AI_AGENT_PERFORMANCE_MODE", "balanced")  # "fast", "balanced", "thorough"

def get_performance_multiplier() -> float:
    """Retourne un multiplicateur basé sur le mode de performance."""
    multipliers = {
        "fast": 0.5,      # Timeouts réduits de 50%
        "balanced": 1.0,  # Timeouts normaux
        "thorough": 2.0   # Timeouts doublés pour plus de thoroughness
    }
    return multipliers.get(PERFORMANCE_MODE, 1.0) 