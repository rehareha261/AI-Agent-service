"""Service pour traiter et persister les webhooks Monday.com."""

from typing import Dict, Any, Optional
from services.database_persistence_service import db_persistence
from utils.logger import get_logger

logger = get_logger(__name__)


class WebhookPersistenceService:
    """Service pour traiter et persister les webhooks Monday.com en temps réel."""
    
    @staticmethod
    async def process_monday_webhook(payload: Dict[str, Any], headers: Dict[str, str] = None, 
                                   signature: str = None) -> Dict[str, Any]:
        """
        Traite un webhook Monday.com et l'enregistre en base.
        
        Args:
            payload: Données du webhook
            headers: Headers HTTP
            signature: Signature de sécurité
            
        Returns:
            Résultat du traitement avec task_id créé
        """
        # Initialiser la persistence si nécessaire
        if not db_persistence.pool:
            await db_persistence.initialize()
        
        webhook_id = None
        task_id = None
        
        try:
            # Validation de base du payload
            if not payload or not isinstance(payload, dict):
                raise ValueError("Payload webhook invalide")
                
            event = payload.get("event", {})
            if not event:
                raise ValueError("Aucun événement dans le payload webhook")
            
            # ✅ CORRECTION: Enregistrer l'événement webhook brut en premier
            webhook_id = await db_persistence._log_webhook_event(
                source="monday",
                event_type=payload.get("type", "unknown"),
                payload=payload,
                headers=headers or {},
                signature=signature
            )
            
            logger.info(f"📨 Webhook Monday.com reçu: {webhook_id}")
            
            # Traitement selon le type d'événement
            event_type = event.get("type", "unknown")
            
            if event_type in ["create_pulse", "update_column_value"]:
                # Événement sur un item (création ou modification)
                task_result = await WebhookPersistenceService._handle_item_event(event, webhook_id)
                
                if task_result:
                    # ✅ CORRECTION: Gérer le nouveau format de retour
                    if isinstance(task_result, dict):
                        task_id = task_result["task_id"]
                        is_existing = task_result.get("existing", False)
                        is_reactivation = task_result.get("is_reactivation", False)
                        
                        # Marquer le webhook comme traité avec succès
                        await db_persistence._mark_webhook_processed(webhook_id, True)
                        
                        return {
                            "success": True,
                            "webhook_id": webhook_id,
                            "task_id": task_id,
                            "task_exists": is_existing and not is_reactivation,  # Ne pas traiter les tâches existantes sauf réactivation
                            "is_reactivation": is_reactivation,
                            "message": "Tâche réactivée" if is_reactivation else ("Tâche mise à jour" if is_existing else "Nouvelle tâche créée")
                        }
                    else:
                        # Ancien format (backward compatibility)
                        task_id = task_result
                        await db_persistence._mark_webhook_processed(webhook_id, True)
                        return {
                            "success": True,
                            "webhook_id": webhook_id,
                            "task_id": task_id,
                            "task_exists": False,
                            "is_reactivation": False,
                            "message": "Nouvelle tâche créée (format legacy)"
                        }
                else:
                    logger.warning("⚠️ Aucune tâche créée/mise à jour")
                    return {
                        "success": False,
                        "webhook_id": webhook_id,
                        "error": "Aucune tâche créée"
                    }
                    
            elif event_type in ["create_update", "create_reply"]:
                # Événement update/commentaire - pas de création de tâche
                await WebhookPersistenceService._handle_update_event(event, webhook_id)
                await db_persistence._mark_webhook_processed(webhook_id, True)
                
                return {
                    "success": True,
                    "webhook_id": webhook_id,
                    "task_id": None,
                    "task_exists": True,  # Ne pas lancer de workflow pour les updates
                    "is_reactivation": False,
                    "message": "Update/commentaire traité"
                }
            else:
                logger.warning(f"⚠️ Type d'événement non supporté: {event_type}")
                await db_persistence._mark_webhook_processed(webhook_id, True, f"Type non supporté: {event_type}")
                
                return {
                    "success": True,
                    "webhook_id": webhook_id,
                    "task_id": None,
                    "task_exists": True,  # Ne pas lancer de workflow
                    "is_reactivation": False,
                    "message": f"Événement ignoré: {event_type}"
                }
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement webhook: {e}")
            
            # Marquer le webhook comme échoué
            if webhook_id:
                await db_persistence._mark_webhook_processed(webhook_id, False, str(e))
            
            return {
                "success": False,
                "webhook_id": webhook_id,
                "task_id": None,
                "task_exists": False,
                "is_reactivation": False,
                "error": str(e),
                "message": "Erreur lors du traitement du webhook"
            }
    
    @staticmethod
    async def _handle_item_event(payload: Dict[str, Any], webhook_id: int) -> Optional[int]:
        """Traite un événement d'item Monday.com (création/modification)."""
        try:
            # Extraire les informations de l'item
            pulse_id = payload.get("pulseId")
            pulse_name = payload.get("pulseName", "Tâche sans titre")
            board_id = payload.get("boardId")
            
            # Rechercher si la tâche existe déjà
            existing_task = await db_persistence._find_task_by_monday_id(pulse_id)
            
            if existing_task:
                # ✅ CORRECTION: Vérifier si c'est un changement de statut significatif
                current_status = payload.get("value", {}).get("label", {}).get("text", "")
                
                # Si c'est un changement vers "En cours" ou "À faire", alors traiter comme une nouvelle tâche
                if current_status.lower() in ["en cours", "à faire", "to do", "in progress", "working"]:
                    logger.info(f"🔄 Tâche {existing_task} réactivée via changement de statut: {current_status}")
                    task_id = await db_persistence._update_task_from_monday(existing_task, payload)
                    # Retourner un dictionnaire avec les infos de réactivation
                    return {"task_id": task_id, "is_reactivation": True, "existing": False}
                else:
                    # Mise à jour standard d'une tâche existante
                    task_id = await db_persistence._update_task_from_monday(existing_task, payload)
                    logger.info(f"📝 Tâche mise à jour: {task_id} - {pulse_name}")
                    # Retourner un dictionnaire indiquant que la tâche existe déjà
                    return {"task_id": task_id, "is_reactivation": False, "existing": True}
            else:
                # Création d'une nouvelle tâche
                task_id = await db_persistence.create_task_from_monday(payload)
                logger.info(f"✨ Nouvelle tâche créée: {task_id} - {pulse_name}")
                # Lier le webhook à la tâche
                await db_persistence._link_webhook_to_task(webhook_id, task_id)
                return {"task_id": task_id, "is_reactivation": False, "existing": False}
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement item event: {e}")
            raise
    
    @staticmethod
    async def _handle_update_event(payload: Dict[str, Any], webhook_id: int):
        """Traite un événement d'update/commentaire Monday.com."""
        try:
            pulse_id = payload.get("pulseId")
            update_text = payload.get("textBody", "")
            update_id = payload.get("updateId") or payload.get("id") or f"update_{pulse_id}_{webhook_id}"
            
            # 🔔 Log de debugging pour tracer la réception
            logger.info(f"🔔 WEBHOOK UPDATE REÇU: pulse_id={pulse_id}, "
                       f"text='{update_text[:50]}...', webhook_id={webhook_id}")
            
            # Rechercher la tâche liée
            task_id = await db_persistence._find_task_by_monday_id(pulse_id)
            
            if not task_id:
                logger.warning(f"⚠️ Tâche non trouvée pour pulse_id {pulse_id}")
                return
            
            # ✅ NOUVEAU: Récupérer les détails de la tâche
            async with db_persistence.pool.acquire() as conn:
                task_details = await conn.fetchrow("""
                    SELECT 
                        tasks_id,
                        monday_item_id,
                        title,
                        description,
                        internal_status,
                        monday_status,
                        repository_url,
                        priority,
                        task_type
                    FROM tasks 
                    WHERE tasks_id = $1
                """, task_id)
            
            if not task_details:
                logger.error(f"❌ Impossible de récupérer les détails de la tâche {task_id}")
                return
            
            # ✅ NOUVEAU: Vérifier si la tâche est terminée
            is_completed = (
                task_details['internal_status'] == 'completed' or
                task_details['monday_status'] == 'Done'
            )
            
            # Logger le commentaire
            await db_persistence.log_application_event(
                task_id=task_id,
                level="INFO",
                source_component="monday_webhook",
                action="item_update_received",
                message=f"Commentaire Monday.com: {update_text[:200]}...",
                metadata={
                    "webhook_id": webhook_id,
                    "full_text": update_text,
                    "monday_pulse_id": pulse_id,
                    "update_id": update_id,
                    "task_completed": is_completed
                }
            )
            
            await db_persistence._link_webhook_to_task(webhook_id, task_id)
            
            # ✅ NOUVEAU: Si tâche terminée, analyser le commentaire
            if is_completed:
                logger.info(f"🔍 Tâche {task_id} terminée - analyse du commentaire pour nouveau workflow")
                
                # Initialiser les services d'analyse
                from services.update_analyzer_service import update_analyzer_service
                from services.workflow_trigger_service import workflow_trigger_service
                
                # Préparer le contexte pour l'analyse
                context = {
                    "task_title": task_details['title'],
                    "task_status": task_details['internal_status'],
                    "monday_status": task_details['monday_status'],
                    "original_description": task_details['description'] or ""
                }
                
                # Analyser l'intention du commentaire
                update_analysis = await update_analyzer_service.analyze_update_intent(
                    update_text=update_text,
                    context=context
                )
                
                logger.info(f"📊 Analyse update: type={update_analysis.type}, "
                          f"requires_workflow={update_analysis.requires_workflow}, "
                          f"confidence={update_analysis.confidence}")
                
                # Enregistrer le trigger dans la DB (même si pas de workflow)
                trigger_id = await db_persistence.create_update_trigger(
                    task_id=task_id,
                    monday_update_id=update_id,
                    webhook_id=webhook_id,
                    update_text=update_text,
                    detected_type=update_analysis.type,
                    confidence=update_analysis.confidence,
                    requires_workflow=update_analysis.requires_workflow,
                    analysis_reasoning=update_analysis.reasoning,
                    extracted_requirements=update_analysis.extracted_requirements
                )
                
                # ✅ NOUVEAU: Si c'est une nouvelle demande, déclencher le workflow
                if update_analysis.requires_workflow and update_analysis.confidence > 0.7:
                    logger.info(f"🚀 Déclenchement d'un nouveau workflow depuis update {update_id}")
                    
                    try:
                        trigger_result = await workflow_trigger_service.trigger_workflow_from_update(
                            task_id=task_id,
                            update_analysis=update_analysis,
                            monday_item_id=task_details['monday_item_id'],
                            update_id=update_id
                        )
                        
                        if trigger_result['success']:
                            logger.info(f"✅ Nouveau workflow déclenché: run_id={trigger_result['run_id']}, "
                                      f"celery_task_id={trigger_result['celery_task_id']}")
                            
                            # Marquer le trigger comme traité avec succès
                            await db_persistence.mark_trigger_as_processed(
                                trigger_id=trigger_id,
                                triggered_workflow=True,
                                new_run_id=trigger_result['run_id'],
                                celery_task_id=trigger_result['celery_task_id']
                            )
                        else:
                            logger.error(f"❌ Échec déclenchement workflow: {trigger_result.get('error')}")
                            # Marquer le trigger comme traité mais sans workflow
                            await db_persistence.mark_trigger_as_processed(
                                trigger_id=trigger_id,
                                triggered_workflow=False
                            )
                            
                    except Exception as e:
                        logger.error(f"❌ Erreur lors du déclenchement du workflow: {e}", exc_info=True)
                        # Marquer le trigger comme traité mais échoué
                        await db_persistence.mark_trigger_as_processed(
                            trigger_id=trigger_id,
                            triggered_workflow=False
                        )
                else:
                    logger.info(f"ℹ️ Commentaire analysé mais pas de workflow requis: "
                              f"type={update_analysis.type}, confidence={update_analysis.confidence}")
                    # Marquer le trigger comme traité (analyse seulement)
                    await db_persistence.mark_trigger_as_processed(
                        trigger_id=trigger_id,
                        triggered_workflow=False
                    )
            else:
                logger.info(f"💬 Commentaire traité pour tâche en cours {task_id} (status={task_details['internal_status']})")
                
        except Exception as e:
            logger.error(f"❌ Erreur traitement update event: {e}", exc_info=True)
            raise
    
    @staticmethod
    async def _handle_board_event(payload: Dict[str, Any], webhook_id: int):
        """Traite un événement de board Monday.com."""
        try:
            board_id = payload.get("boardId")
            board_name = payload.get("boardName", "Board sans nom")
            
            # Logger comme événement système
            await db_persistence.log_application_event(
                level="INFO",
                source_component="monday_webhook",
                action="board_event",
                message=f"Événement board Monday.com: {board_name}",
                metadata={
                    "webhook_id": webhook_id,
                    "board_id": board_id,
                    "board_name": board_name
                }
            )
            
            logger.info(f"📋 Événement board traité: {board_name}")
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement board event: {e}")
            raise


# Instance globale
webhook_persistence = WebhookPersistenceService() 