"""Service de gestion des validations humaines avec persistance en base de données."""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import asyncpg
from models.schemas import (
    HumanValidationRequest, 
    HumanValidationResponse, 
    HumanValidationStatus,
    HumanValidationSummary
)
from utils.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class HumanValidationService:
    """Service pour gérer les validations humaines avec base de données."""
    
    def __init__(self):
        self.db_pool = None
    
    def _validate_files_modified(self, files_modified: Any) -> List[str]:
        """
        Valide et normalise le champ files_modified pour s'assurer que c'est une liste de strings.
        
        Args:
            files_modified: Peut être list, dict, ou autre type
            
        Returns:
            Liste de strings (noms de fichiers)
        """
        try:
            # Cas 1: Déjà une liste
            if isinstance(files_modified, list):
                # S'assurer que tous les éléments sont des strings
                validated = [str(f) for f in files_modified if f]
                logger.info(f"✅ files_modified validé: {len(validated)} fichiers (était déjà liste)")
                return validated
            
            # Cas 2: Dict (code_changes) - extraire les clés
            elif isinstance(files_modified, dict):
                validated = list(files_modified.keys())
                logger.warning(f"⚠️ files_modified était un dict - conversion en liste: {len(validated)} fichiers")
                return validated
            
            # Cas 3: String unique
            elif isinstance(files_modified, str):
                logger.warning(f"⚠️ files_modified était un string - conversion en liste: 1 fichier")
                return [files_modified]
            
            # Cas 4: None ou vide
            elif not files_modified:
                logger.warning("⚠️ files_modified était None/vide - retourne liste vide")
                return []
            
            # Cas 5: Type inattendu
            else:
                logger.error(f"❌ Type inattendu pour files_modified: {type(files_modified)} - retourne liste vide")
                return []
                
        except Exception as e:
            logger.error(f"❌ Erreur validation files_modified: {e} - retourne liste vide")
            return []
    
    async def init_db_pool(self):
        """Initialise le pool de connexions à la base de données."""
        if not self.db_pool:
            try:
                self.db_pool = await asyncpg.create_pool(
                    host=settings.db_host,
                    port=settings.db_port,
                    user=settings.db_user,
                    password=settings.db_password,
                    database=settings.db_name,
                    min_size=2,
                    max_size=10
                )
                logger.info("✅ Pool de connexions validation humaine initialisé")
            except Exception as e:
                logger.error(f"❌ Erreur initialisation pool DB: {e}")
                raise
    
    async def close_db_pool(self):
        """Ferme le pool de connexions."""
        if self.db_pool:
            await self.db_pool.close()
            self.db_pool = None
    
    async def create_validation_request(
        self, 
        validation_request: HumanValidationRequest,
        task_id: int,
        task_run_id: Optional[int] = None,
        run_step_id: Optional[int] = None
    ) -> bool:
        """
        Crée une demande de validation en base de données.
        
        Args:
            validation_request: Demande de validation
            task_id: ID de la tâche
            task_run_id: ID du run (optionnel)
            run_step_id: ID de l'étape (optionnel)
            
        Returns:
            True si créé avec succès
        """
        if not self.db_pool:
            await self.init_db_pool()
        
        try:
            async with self.db_pool.acquire() as conn:
                # ✅ CORRECTION: pr_info est maintenant déjà un JSON string grâce au validateur Pydantic
                # Plus besoin de le convertir en dict ici
                # Les champs generated_code, test_results et pr_info sont maintenant des JSON strings
                
                # ✅ VALIDATION CRITIQUE: S'assurer que files_modified est toujours une liste de strings
                files_modified_validated = self._validate_files_modified(validation_request.files_modified)
                
                # Insérer la validation
                await conn.execute("""
                    INSERT INTO human_validations (
                        validation_id, task_id, task_run_id, run_step_id,
                        task_title, task_description, original_request,
                        status, generated_code, code_summary, files_modified,
                        implementation_notes, test_results, pr_info,
                        workflow_id, requested_by, created_at, expires_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                """, 
                    validation_request.validation_id,
                    task_id,
                    task_run_id,
                    run_step_id,
                    validation_request.task_title,
                    validation_request.original_request[:1000] if validation_request.original_request else None,  # Limite pour task_description 
                    validation_request.original_request,
                    HumanValidationStatus.PENDING.value,
                    validation_request.generated_code,  # ✅ Déjà un JSON string
                    validation_request.code_summary,
                    files_modified_validated,  # ✅ Utiliser la version validée
                    validation_request.implementation_notes,
                    validation_request.test_results,  # ✅ Déjà un JSON string
                    validation_request.pr_info,  # ✅ Déjà un JSON string (ou None)
                    validation_request.workflow_id,
                    validation_request.requested_by,
                    validation_request.created_at,
                    validation_request.expires_at
                )
                
                logger.info(f"✅ Validation {validation_request.validation_id} créée en base")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erreur création validation {validation_request.validation_id}: {e}")
            return False
    
    async def get_validation_by_id(self, validation_id: str) -> Optional[HumanValidationRequest]:
        """Récupère une validation par son ID."""
        if not self.db_pool:
            await self.init_db_pool()
        
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM human_validations 
                    WHERE validation_id = $1
                """, validation_id)
                
                if not row:
                    return None
                
                # Reconstituer l'objet PullRequestInfo si présent
                pr_info = None
                if row['pr_info']:
                    from models.schemas import PullRequestInfo
                    pr_data = row['pr_info']
                    pr_info = PullRequestInfo(
                        number=pr_data.get('number', 0),
                        title=pr_data.get('title', ''),
                        url=pr_data.get('url', ''),
                        branch=pr_data.get('branch', ''),
                        base_branch=pr_data.get('base_branch', ''),
                        status=pr_data.get('status', ''),
                        created_at=datetime.fromisoformat(pr_data.get('created_at', datetime.now(timezone.utc).isoformat()))
                    )
                
                # Créer l'objet HumanValidationRequest
                validation = HumanValidationRequest(
                    validation_id=row['validation_id'],
                    workflow_id=row['workflow_id'],
                    task_id=str(row['task_id']),  # Convertir en string comme attendu par le modèle
                    task_title=row['task_title'],
                    generated_code=row['generated_code'],
                    code_summary=row['code_summary'],
                    files_modified=list(row['files_modified']),
                    original_request=row['original_request'],
                    implementation_notes=row['implementation_notes'],
                    test_results=row['test_results'],
                    pr_info=pr_info,
                    created_at=row['created_at'],
                    expires_at=row['expires_at'],
                    requested_by=row['requested_by']
                )
                
                return validation
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération validation {validation_id}: {e}")
            return None
    
    async def list_pending_validations(self, include_expired: bool = False) -> List[HumanValidationSummary]:
        """Liste les validations en attente."""
        if not self.db_pool:
            await self.init_db_pool()
        
        try:
            async with self.db_pool.acquire() as conn:
                # Marquer d'abord les validations expirées
                await conn.execute("SELECT mark_expired_validations()")
                
                # Construire la requête
                where_clause = "WHERE status = 'pending'"
                if include_expired:
                    where_clause = "WHERE status IN ('pending', 'expired')"
                
                rows = await conn.fetch(f"""
                    SELECT 
                        validation_id,
                        task_title,
                        status,
                        created_at,
                        expires_at,
                        array_length(files_modified, 1) as files_count,
                        pr_info->>'url' as pr_url,
                        CASE 
                            WHEN expires_at IS NOT NULL AND expires_at < NOW() + INTERVAL '1 hour'
                            THEN TRUE 
                            ELSE FALSE 
                        END as is_urgent,
                        CASE 
                            WHEN test_results IS NOT NULL AND (test_results->>'success')::boolean = FALSE
                            THEN TRUE
                            ELSE FALSE
                        END as has_test_failures
                    FROM human_validations
                    {where_clause}
                    ORDER BY 
                        CASE WHEN status = 'pending' THEN 0 ELSE 1 END,
                        CASE WHEN expires_at IS NOT NULL AND expires_at < NOW() + INTERVAL '1 hour' THEN 0 ELSE 1 END,
                        created_at DESC
                """)
                
                validations = []
                for row in rows:
                    # Déterminer le statut (peut avoir changé avec mark_expired_validations)
                    status = HumanValidationStatus.EXPIRED if row['status'] == 'expired' else HumanValidationStatus.PENDING
                    
                    summary = HumanValidationSummary(
                        validation_id=row['validation_id'],
                        task_title=row['task_title'],
                        status=status,
                        created_at=row['created_at'],
                        expires_at=row['expires_at'],
                        files_count=row['files_count'] or 0,
                        pr_url=row['pr_url'],
                        is_urgent=row['is_urgent'],
                        has_test_failures=row['has_test_failures']
                    )
                    validations.append(summary)
                
                return validations
                
        except Exception as e:
            logger.error(f"❌ Erreur liste validations: {e}")
            return []
    
    async def submit_validation_response(self, validation_id: str, response: HumanValidationResponse) -> bool:
        """Soumet une réponse de validation."""
        if not self.db_pool:
            await self.init_db_pool()
        
        try:
            async with self.db_pool.acquire() as conn:
                async with conn.transaction():
                    # Vérifier que la validation existe et est en attente
                    validation_row = await conn.fetchrow("""
                        SELECT human_validations_id, status, created_at 
                        FROM human_validations 
                        WHERE validation_id = $1
                    """, validation_id)
                    
                    if not validation_row:
                        logger.error(f"❌ Validation {validation_id} non trouvée")
                        return False
                    
                    if validation_row['status'] != 'pending':
                        logger.error(f"❌ Validation {validation_id} n'est plus en attente (statut: {validation_row['status']})")
                        return False
                    
                    # Calculer la durée de validation
                    validation_duration = None
                    if validation_row['created_at']:
                        # ✅ CORRECTION: S'assurer que les deux datetimes ont la même timezone-awareness
                        from datetime import timezone
                        
                        # Récupérer created_at de la DB (timezone-aware en UTC si configuré dans PostgreSQL)
                        created_at = validation_row['created_at']
                        
                        # S'assurer que validated_at est aussi timezone-aware
                        validated_at = response.validated_at
                        if validated_at.tzinfo is None:
                            # Si naive, ajouter UTC
                            validated_at = validated_at.replace(tzinfo=timezone.utc)
                        
                        # S'assurer que created_at est aussi timezone-aware
                        if created_at.tzinfo is None:
                            # Si naive, ajouter UTC
                            created_at = created_at.replace(tzinfo=timezone.utc)
                        
                        duration_delta = validated_at - created_at
                        validation_duration = int(duration_delta.total_seconds())
                    
                    # Insérer la réponse
                    await conn.execute("""
                        INSERT INTO human_validation_responses (
                            human_validation_id, validation_id, response_status,
                            comments, suggested_changes, approval_notes,
                            validated_by, validated_at, should_merge, should_continue_workflow,
                            validation_duration_seconds
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """,
                        validation_row['human_validations_id'],
                        validation_id,
                        response.status.value,
                        response.comments,
                        response.suggested_changes,
                        response.approval_notes,
                        response.validated_by,
                        response.validated_at,
                        response.should_merge,
                        response.should_continue_workflow,
                        validation_duration
                    )
                    
                    # Le statut sera mis à jour automatiquement par le trigger
                    logger.info(f"✅ Réponse validation {validation_id} soumise: {response.status.value}")
                    return True
                    
        except Exception as e:
            logger.error(f"❌ Erreur soumission réponse {validation_id}: {e}")
            return False
    
    async def get_validation_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques de validation."""
        if not self.db_pool:
            await self.init_db_pool()
        
        try:
            async with self.db_pool.acquire() as conn:
                # Utiliser la fonction SQL dédiée
                row = await conn.fetchrow("SELECT * FROM get_validation_stats()")
                
                return {
                    "total_validations": row['total_validations'] or 0,
                    "pending_validations": row['pending_validations'] or 0,
                    "approved_validations": row['approved_validations'] or 0,
                    "rejected_validations": row['rejected_validations'] or 0,
                    "expired_validations": row['expired_validations'] or 0,
                    "avg_validation_time_minutes": float(row['avg_validation_time_minutes'] or 0),
                    "urgent_validations": row['urgent_validations'] or 0,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur statistiques validation: {e}")
            return {
                "total_validations": 0,
                "pending_validations": 0,
                "approved_validations": 0,
                "rejected_validations": 0,
                "expired_validations": 0,
                "avg_validation_time_minutes": 0.0,
                "urgent_validations": 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def create_validation_action(
        self,
        validation_id: str,
        action_type: str,
        action_data: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """
        Crée une action post-validation (merge PR, update Monday, etc.).
        
        Args:
            validation_id: ID de la validation
            action_type: Type d'action ('merge_pr', 'reject_pr', 'update_monday', 'cleanup_branch', 'notify_user')
            action_data: Données spécifiques à l'action
            
        Returns:
            ID de l'action créée ou None si échec
        """
        if not self.db_pool:
            await self.init_db_pool()
        
        # Valider le type d'action
        valid_action_types = ['merge_pr', 'reject_pr', 'update_monday', 'cleanup_branch', 'notify_user']
        if action_type not in valid_action_types:
            logger.error(f"❌ Type d'action invalide: {action_type}. Valides: {valid_action_types}")
            return None
        
        try:
            async with self.db_pool.acquire() as conn:
                # Récupérer l'ID de validation pour la référence
                validation_row = await conn.fetchrow("""
                    SELECT human_validations_id FROM human_validations
                    WHERE validation_id = $1
                """, validation_id)
                
                if not validation_row:
                    logger.error(f"❌ Validation {validation_id} non trouvée")
                    return None
                
                # Insérer l'action
                import json
                action_id = await conn.fetchval("""
                    INSERT INTO validation_actions (
                        human_validation_id, validation_id, action_type,
                        action_status, action_data, created_at
                    ) VALUES ($1, $2, $3, $4, $5, NOW())
                    RETURNING validation_actions_id
                """,
                    validation_row['human_validations_id'],
                    validation_id,
                    action_type,
                    'pending',
                    json.dumps(action_data) if action_data else None
                )
                
                logger.info(f"✅ Action {action_type} créée pour validation {validation_id}: ID={action_id}")
                return action_id
                
        except Exception as e:
            logger.error(f"❌ Erreur création action pour {validation_id}: {e}")
            return None
    
    async def update_validation_action(
        self,
        action_id: int,
        status: str,
        result_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        merge_commit_hash: Optional[str] = None,
        merge_commit_url: Optional[str] = None
    ) -> bool:
        """
        Met à jour le statut d'une action de validation.
        
        Args:
            action_id: ID de l'action
            status: Nouveau statut ('pending', 'in_progress', 'completed', 'failed', 'cancelled')
            result_data: Données de résultat
            error_message: Message d'erreur si échec
            merge_commit_hash: Hash du commit de merge (si applicable)
            merge_commit_url: URL du commit de merge (si applicable)
            
        Returns:
            True si succès, False sinon
        """
        if not self.db_pool:
            await self.init_db_pool()
        
        # Valider le statut
        valid_statuses = ['pending', 'in_progress', 'completed', 'failed', 'cancelled']
        if status not in valid_statuses:
            logger.error(f"❌ Statut d'action invalide: {status}. Valides: {valid_statuses}")
            return False
        
        try:
            async with self.db_pool.acquire() as conn:
                import json
                
                # Mettre à jour les timestamps selon le statut
                update_query = """
                    UPDATE validation_actions
                    SET action_status = $2,
                        result_data = $3,
                        error_message = $4,
                        merge_commit_hash = $5,
                        merge_commit_url = $6,
                """
                
                if status == 'in_progress':
                    update_query += "started_at = NOW(),"
                elif status in ['completed', 'failed', 'cancelled']:
                    update_query += "completed_at = NOW(),"
                
                # Retirer la virgule finale et ajouter WHERE
                update_query = update_query.rstrip(',') + " WHERE validation_actions_id = $1"
                
                await conn.execute(
                    update_query,
                    action_id,
                    status,
                    json.dumps(result_data) if result_data else None,
                    error_message,
                    merge_commit_hash,
                    merge_commit_url
                )
                
                logger.info(f"✅ Action {action_id} mise à jour: statut={status}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour action {action_id}: {e}")
            return False
    
    async def get_validation_actions(self, validation_id: str) -> List[Dict[str, Any]]:
        """
        Récupère toutes les actions associées à une validation.
        
        Args:
            validation_id: ID de la validation
            
        Returns:
            Liste des actions
        """
        if not self.db_pool:
            await self.init_db_pool()
        
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        validation_actions_id,
                        action_type,
                        action_status,
                        action_data,
                        result_data,
                        merge_commit_hash,
                        merge_commit_url,
                        created_at,
                        started_at,
                        completed_at,
                        error_message,
                        retry_count
                    FROM validation_actions
                    WHERE validation_id = $1
                    ORDER BY created_at DESC
                """, validation_id)
                
                actions = []
                for row in rows:
                    actions.append({
                        "action_id": row['validation_actions_id'],
                        "action_type": row['action_type'],
                        "status": row['action_status'],
                        "action_data": row['action_data'],
                        "result_data": row['result_data'],
                        "merge_commit_hash": row['merge_commit_hash'],
                        "merge_commit_url": row['merge_commit_url'],
                        "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                        "started_at": row['started_at'].isoformat() if row['started_at'] else None,
                        "completed_at": row['completed_at'].isoformat() if row['completed_at'] else None,
                        "error_message": row['error_message'],
                        "retry_count": row['retry_count']
                    })
                
                return actions
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération actions pour {validation_id}: {e}")
            return []
    
    async def wait_for_validation_response(self, validation_id: str, timeout_minutes: int = 10) -> Optional[HumanValidationResponse]:
        """
        Attend une réponse de validation avec polling de la base de données.
        
        Args:
            validation_id: ID de la validation
            timeout_minutes: Timeout en minutes
            
        Returns:
            Réponse de validation ou None si timeout
        """
        timeout_seconds = timeout_minutes * 60
        check_interval = 10  # Vérifier toutes les 10 secondes
        elapsed = 0
        
        while elapsed < timeout_seconds:
            if not self.db_pool:
                await self.init_db_pool()
            
            try:
                async with self.db_pool.acquire() as conn:
                    # Vérifier s'il y a une réponse
                    row = await conn.fetchrow("""
                        SELECT hvr.*, hv.status as validation_status
                        FROM human_validation_responses hvr
                        JOIN human_validations hv ON hvr.human_validation_id = hv.human_validations_id
                        WHERE hvr.validation_id = $1
                        ORDER BY hvr.validated_at DESC
                        LIMIT 1
                    """, validation_id)
                    
                    if row:
                        # Créer l'objet de réponse
                        response = HumanValidationResponse(
                            validation_id=row['validation_id'],
                            status=HumanValidationStatus(row['response_status']),
                            comments=row['comments'],
                            suggested_changes=row['suggested_changes'],
                            approval_notes=row['approval_notes'],
                            validated_by=row['validated_by'],
                            validated_at=row['validated_at'],
                            should_merge=row['should_merge'],
                            should_continue_workflow=row['should_continue_workflow']
                        )
                        
                        logger.info(f"✅ Réponse reçue pour validation {validation_id}: {response.status.value}")
                        return response
                    
                    # Vérifier si la validation a expiré
                    validation_status = await conn.fetchval("""
                        SELECT status FROM human_validations WHERE validation_id = $1
                    """, validation_id)
                    
                    if validation_status == 'expired':
                        logger.warning(f"⏰ Validation {validation_id} expirée")
                        return None
                        
            except Exception as e:
                logger.error(f"❌ Erreur lors de la vérification de réponse {validation_id}: {e}")
            
            # Attendre avant la prochaine vérification
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            
            # Log de progression toutes les minutes
            if elapsed % 60 == 0:
                logger.info(f"⏳ Attente validation {validation_id}: {elapsed//60}min/{timeout_minutes}min")
        
        # Timeout atteint
        logger.warning(f"⏰ Timeout validation humaine: {validation_id}")
        return None


# Instance globale du service
validation_service = HumanValidationService() 