"""Configuration des limites et seuils pour les workflows."""

class WorkflowLimits:
    """Limites et seuils configurables pour les workflows."""
    
    # Limites de sécurité
    MAX_NODES_SAFETY_LIMIT = 35  # ✅ AUGMENTÉ: Permet les boucles debug + validation Monday (était 25)
    MAX_DEBUG_ATTEMPTS = 2       # ✅ RÉDUIT: Nombre maximum de tentatives de debug (réduit de 3 à 2)
    MAX_RETRY_ATTEMPTS = 2       # ✅ RÉDUIT: Nombre maximum de retry pour les opérations (réduit de 3 à 2)
    
    # Timeouts (en secondes)
    WORKFLOW_TIMEOUT = 1200      # ✅ RÉDUIT: 20 minutes par workflow maximum (réduit de 1h à 20min)
    NODE_TIMEOUT = 300           # ✅ RÉDUIT: 5 minutes par nœud maximum (réduit de 10min à 5min)
    API_REQUEST_TIMEOUT = 120    # 2 minutes pour les requêtes API
    
    # Limites de ressources
    MAX_FILE_SIZE_MB = 50        # Taille maximum des fichiers traités
    MAX_LOG_SIZE_MB = 100        # Taille maximum des logs
    MAX_CONCURRENT_WORKFLOWS = 10 # Nombre maximum de workflows simultanés
    
    # Seuils qualité
    MIN_QA_SCORE = 55           # Score QA minimum pour passer
    MAX_CRITICAL_ISSUES = 5     # Nombre maximum de problèmes critiques
    
    # Configuration monitoring
    MONITORING_INTERVAL = 30    # Intervalle de monitoring en secondes
    ALERT_THRESHOLD_ERROR_RATE = 0.1  # Seuil d'alerte pour le taux d'erreur (10%)
    
    @classmethod
    def get_limits_dict(cls) -> dict:
        """Retourne toutes les limites sous forme de dictionnaire."""
        return {
            "max_nodes": cls.MAX_NODES_SAFETY_LIMIT,
            "max_debug_attempts": cls.MAX_DEBUG_ATTEMPTS,
            "max_retry_attempts": cls.MAX_RETRY_ATTEMPTS,
            "workflow_timeout": cls.WORKFLOW_TIMEOUT,
            "node_timeout": cls.NODE_TIMEOUT,
            "api_timeout": cls.API_REQUEST_TIMEOUT,
            "max_file_size_mb": cls.MAX_FILE_SIZE_MB,
            "max_log_size_mb": cls.MAX_LOG_SIZE_MB,
            "max_concurrent": cls.MAX_CONCURRENT_WORKFLOWS,
            "min_qa_score": cls.MIN_QA_SCORE,
            "max_critical_issues": cls.MAX_CRITICAL_ISSUES,
            "monitoring_interval": cls.MONITORING_INTERVAL,
            "alert_threshold": cls.ALERT_THRESHOLD_ERROR_RATE
        }
        
    @classmethod
    def validate_limits(cls) -> bool:
        """Valide que toutes les limites sont dans des plages acceptables."""
        validations = [
            cls.MAX_NODES_SAFETY_LIMIT > 0,
            cls.MAX_DEBUG_ATTEMPTS > 0,
            cls.WORKFLOW_TIMEOUT > 60,  # Au moins 1 minute
            cls.NODE_TIMEOUT > 10,      # Au moins 10 secondes
            cls.MIN_QA_SCORE >= 0 and cls.MIN_QA_SCORE <= 100,
            cls.MAX_CRITICAL_ISSUES >= 0,
            cls.MONITORING_INTERVAL > 0,
            cls.ALERT_THRESHOLD_ERROR_RATE >= 0 and cls.ALERT_THRESHOLD_ERROR_RATE <= 1
        ]
        return all(validations) 