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
            
            # Rechercher la tâche liée
            task_id = await db_persistence._find_task_by_monday_id(pulse_id)
            
            if task_id:
                # Logger le commentaire comme événement applicatif
                await db_persistence.log_application_event(
                    task_id=task_id,
                    level="INFO",
                    source_component="monday_webhook",
                    action="item_update_received",
                    message=f"Commentaire Monday.com: {update_text[:200]}...",
                    metadata={
                        "webhook_id": webhook_id,
                        "full_text": update_text,
                        "monday_pulse_id": pulse_id
                    }
                )
                
                # Lier le webhook
                await db_persistence._link_webhook_to_task(webhook_id, task_id)
                
                logger.info(f"💬 Commentaire Monday traité pour tâche {task_id}")
            else:
                logger.warning(f"⚠️ Tâche non trouvée pour pulse_id {pulse_id}")
                
        except Exception as e:
            logger.error(f"❌ Erreur traitement update event: {e}")
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