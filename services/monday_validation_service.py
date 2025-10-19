"""Service de validation humaine via les updates Monday.com."""

import asyncio
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from models.schemas import HumanValidationStatus, HumanValidationResponse
from tools.monday_tool import MondayTool
from services.intelligent_reply_analyzer import intelligent_reply_analyzer, IntentionType
from utils.logger import get_logger

logger = get_logger(__name__)


class MondayValidationService:
    """Service pour gérer la validation humaine via les updates Monday.com."""
    
    def __init__(self):
        self.monday_tool = MondayTool()
        # ✅ CORRECTION: Initialiser le dictionnaire à la bonne place
        self.pending_validations = {}
    
    def _safe_get_test_success(self, test_results) -> bool:
        """Extrait le statut de succès des tests de manière sécurisée."""
        if isinstance(test_results, dict):
            return test_results.get("success", False)
        elif isinstance(test_results, list) and test_results:
            # Si c'est une liste, considérer comme succès si tous les tests passent
            return all(item.get("passed", False) if isinstance(item, dict) else False for item in test_results)
        elif hasattr(test_results, 'success'):
            return getattr(test_results, 'success', False)
        else:
            return False
    
    def _build_validation_message(self, workflow_results: Dict[str, Any]) -> str:
        """
        Construit le message de validation à poster dans Monday.com.
        
        Args:
            workflow_results: Résultats du workflow
            
        Returns:
            Message formaté pour Monday.com
        """
        # Récupération des informations depuis workflow_results
        task_title = workflow_results.get("task_title", "Tâche sans titre")
        environment_path = workflow_results.get("environment_path", "Non disponible")
        modified_files = workflow_results.get("modified_files", [])
        implementation_success = workflow_results.get("implementation_success", False)
        test_success = workflow_results.get("test_success", False)
        test_executed = workflow_results.get("test_executed", False)
        pr_created = workflow_results.get("pr_created", False)
        
        # Construction du message
        message = f"""🤖 **WORKFLOW TERMINÉ - VALIDATION REQUISE** ⚠️

**Tâche**: {task_title}

📝 **Progression du workflow**:
• ✅ Environnement configuré: {environment_path}
"""
        
        # Ajouter les fichiers modifiés
        if modified_files:
            message += f"• ✅ Fichiers modifiés: {', '.join(modified_files)}\n"
        else:
            message += "• ⚠️ Aucun fichier modifié détecté\n"
        
        # Statut de l'implémentation
        if implementation_success:
            message += "• ✅ Implémentation terminée avec succès\n"
        else:
            message += "• ❌ Implémentation échouée\n"
        
        # Statut des tests
        if test_executed:
            if test_success:
                message += "• ✅ Tests exécutés avec succès\n"
            else:
                message += "• ⚠️ Tests exécutés avec des erreurs\n"
        else:
            message += "• ⚠️ Aucun test exécuté\n"
        
        # Statut de la Pull Request
        if pr_created:
            # ✅ CORRECTION: Simplifier la récupération de l'URL PR
            pr_url = workflow_results.get("pr_url")
            if not pr_url:
                pr_info = workflow_results.get("pr_info")
                if isinstance(pr_info, dict):
                    pr_url = pr_info.get("url", "")
                elif pr_info:  # C'est un objet (PullRequestInfo)
                    pr_url = getattr(pr_info, "url", "")
            
            if pr_url:
                message += f"• ✅ Pull Request créée: {pr_url}\n"
            else:
                message += "• ✅ Pull Request créée\n"
        else:
            message += "• ❌ Pull Request non créée\n"
        
        # Instructions de validation
        message += """
==================================================
**🤝 VALIDATION HUMAINE REQUISE**

**Répondez à cette update avec**:
• **'oui'** ou **'valide'** → Merge automatique
• **'non'** ou **'debug'** → Debug avec LLM OpenAI

⏰ *Timeout: 60 minutes*"""
        
        return message

    async def post_validation_update(self, item_id: str, workflow_results: Dict[str, Any]) -> str:
        """
        Poste une update de validation dans Monday.com.
        
        Args:
            item_id: ID de l'item Monday.com
            workflow_results: Résultats du workflow à inclure
            
        Returns:
            ID de l'update créée ou ID de fallback en cas d'erreur
        """
        try:
            # Créer le message de validation
            comment = self._build_validation_message(workflow_results)
            
            logger.info(f"📝 Création update de validation pour item {item_id}")
            
            # ✅ AMÉLIORATION: Tentative de création d'update avec gestion des permissions
            result = await self.monday_tool._arun(
                action="add_comment",
                item_id=item_id,
                comment=comment
            )
            
            # ✅ GESTION ROBUSTE DES ERREURS DE PERMISSIONS
            if not result.get("success", False):
                error_type = result.get("error_type", "unknown")
                error_message = result.get("error", "Erreur inconnue")
                
                if error_type == "permissions":
                    logger.warning(f"⚠️ Permissions insuffisantes Monday.com pour item {item_id}")
                    logger.warning(f"⚠️ {error_message}")
                    
                    # ✅ FALLBACK: Utiliser un ID d'update alternatif
                    update_id = f"failed_update_{item_id}"
                    logger.info(f"📝 Utilisation update_id alternatif: {update_id}")
                    
                    # Enregistrer la validation en attente sans Monday.com
                    self.pending_validations[update_id] = {
                        "item_id": item_id,
                        "message": comment,
                        "timestamp": datetime.now().isoformat(),
                        "fallback_mode": True,
                        "permissions_error": True,
                        "error": error_message,
                        "workflow_results": workflow_results  # ✅ CORRECTION: Ajouter workflow_results
                    }
                    
                    return update_id
                    
                elif error_type in ["auth", "graphql"]:
                    # Erreurs d'authentification ou GraphQL - utiliser fallback aussi
                    logger.error(f"❌ Erreur Monday.com ({error_type}): {error_message}")
                    update_id = f"error_update_{item_id}"
                    
                    self.pending_validations[update_id] = {
                        "item_id": item_id,
                        "message": comment,
                        "timestamp": datetime.now().isoformat(),
                        "fallback_mode": True,
                        "api_error": True,
                        "error": error_message,
                        "workflow_results": workflow_results  # ✅ CORRECTION: Ajouter workflow_results
                    }
                    
                    return update_id
                    
                else:
                    # Autres erreurs - lever l'exception
                    raise Exception(f"Erreur Monday.com: {error_message}")
            
            # ✅ SUCCÈS: Update créée avec succès
            update_id = result.get("update_id") or result.get("comment_id") or f"success_update_{item_id}"
            
            logger.info(f"✅ Update de validation créée avec succès: {update_id}")
            
            # Enregistrer la validation en attente avec validation_id depuis workflow_results
            validation_id_from_results = workflow_results.get("validation_id")
            
            self.pending_validations[str(update_id)] = {
                "item_id": item_id,
                "message": comment,
                "timestamp": datetime.now().isoformat(),
                "fallback_mode": False,
                "permissions_error": False,
                "workflow_results": workflow_results,  # ✅ CORRECTION: Ajouter workflow_results pour le contexte
                "validation_id": validation_id_from_results  # ✅ NOUVEAU: Stocker validation_id pour les réponses DB
            }
            
            return str(update_id)
            
        except Exception as e:
            logger.error(f"❌ Exception lors de la création d'update Monday.com: {e}")
            
            # ✅ FALLBACK EXCEPTION: Mode de secours complet
            update_id = f"exception_update_{item_id}"
            
            self.pending_validations[update_id] = {
                "item_id": item_id,
                "message": comment if 'comment' in locals() else "Message de validation indisponible",
                "timestamp": datetime.now().isoformat(),
                "fallback_mode": True,
                "exception_error": True,
                "error": str(e),
                "workflow_results": workflow_results if 'workflow_results' in locals() else {}  # ✅ CORRECTION: Ajouter workflow_results
            }
            
            return update_id
    
    async def check_for_human_replies(self, update_id: str, timeout_minutes: int = 10) -> Optional[HumanValidationResponse]:
        """
        Vérifie les replies humaines sur l'update de validation.
        
        Args:
            update_id: ID de l'update à surveiller
            timeout_minutes: Timeout en minutes
            
        Returns:
            Réponse de validation ou None si timeout
        """
        update_key = str(update_id)
        
        # ✅ CORRECTION CRITIQUE: Récupérer le contexte si absent
        if update_key not in self.pending_validations:
            logger.warning(f"⚠️ Update {update_id} non trouvée dans pending_validations - tentative de récupération")
            
            # Essayer de reconstituer le contexte depuis Monday.com
            recovered_validation = await self._recover_validation_context(update_id)
            if recovered_validation:
                self.pending_validations[update_key] = recovered_validation
                logger.info(f"✅ Contexte de validation récupéré pour {update_id}")
            else:
                logger.error(f"❌ Impossible de récupérer le contexte pour {update_id}")
                return None
        
        validation_data = self.pending_validations[update_key]
        item_id = validation_data.get("item_id")
        
        timeout_seconds = timeout_minutes * 60
        
        # ✅ AMÉLIORATION: Intervalle de polling réduit et configurable (15s → 5s)
        check_interval = int(os.getenv("MONDAY_VALIDATION_CHECK_INTERVAL", "5"))  # Défaut: 5 secondes
        
        # ✅ CORRECTION: Adapter la logique d'abandon selon le timeout et l'intervalle
        if timeout_minutes <= 10:
            max_consecutive_no_changes = max(4, int(120 / check_interval))  # ~2 minutes
        else:
            max_consecutive_no_changes = max(10, int(300 / check_interval))  # ~5 minutes
        
        logger.info(f"⏳ Attente de reply humaine sur update {update_id} (timeout: {timeout_minutes}min, check_interval: {check_interval}s, max_no_changes: {max_consecutive_no_changes})")
        
        # ✅ CORRECTION: Ajouter une vérification initiale immédiate avec retry
        created_at = datetime.now()
        created_at_str = validation_data.get("timestamp") or validation_data.get("created_at")
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            except Exception as e:
                logger.warning(f"⚠️ Erreur parsing timestamp: {e}")
                created_at = datetime.now()
        
        # ✅ NOUVEAU: Faire 3 vérifications rapides au démarrage (0s, 2s, 5s)
        for check_delay in [0, 2, 5]:
            if check_delay > 0:
                await asyncio.sleep(check_delay)
                
            try:
                initial_check = await self._get_item_updates(item_id)
                if initial_check:
                    immediate_reply = self._find_human_reply(update_id, initial_check, created_at)
                    if immediate_reply:
                        logger.info(f"⚡ Réponse humaine trouvée après {check_delay}s!")
                        validation_context = self._prepare_analysis_context(validation_data)
                        response = await self._parse_human_reply(immediate_reply, update_id, validation_context)
                        self.pending_validations[update_id]["status"] = response.status.value
                        self.pending_validations[update_id]["response"] = response
                        return response
            except Exception as e:
                logger.warning(f"⚠️ Erreur lors de la vérification à {check_delay}s: {e}")
        
        # Boucle d'attente principale
        elapsed = 0
        last_update_count = 0  # Pour détecter de nouvelles updates
        consecutive_no_changes = 0  # Compteur de vérifications sans changement
        
        while elapsed < timeout_seconds:
            try:
                # Récupérer les updates récentes de l'item
                recent_updates = await self._get_item_updates(item_id)
                
                # ✅ NOUVELLE LOGIQUE: Détecter si de nouvelles updates sont arrivées
                current_update_count = len(recent_updates) if recent_updates else 0
                
                if current_update_count > last_update_count:
                    logger.info(f"📬 Nouvelles updates détectées: {current_update_count} (était {last_update_count})")
                    last_update_count = current_update_count
                    consecutive_no_changes = 0  # Reset du compteur
                    
                    # Chercher des replies à notre update
                    created_at_str = validation_data.get("timestamp") or validation_data.get("created_at")
                    if created_at_str:
                        try:
                            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        except Exception as e:
                            logger.warning(f"⚠️ Erreur parsing timestamp {created_at_str}: {e}")
                            created_at = datetime.now()
                    else:
                        created_at = datetime.now()
                    human_reply = self._find_human_reply(update_id, recent_updates, created_at)
                    
                    if human_reply:
                        # Préparer le contexte pour l'analyse intelligente
                        validation_context = self._prepare_analysis_context(validation_data)
                        
                        # Analyser la réponse humaine avec IA
                        response = await self._parse_human_reply(human_reply, update_id, validation_context)
                        
                        # Mettre à jour le statut
                        self.pending_validations[update_id]["status"] = response.status.value
                        self.pending_validations[update_id]["response"] = response
                        
                        logger.info(f"✅ Reply humaine analysée: {response.status.value} (confiance: {getattr(response, 'analysis_confidence', 'N/A')})")
                        return response
                else:
                    consecutive_no_changes += 1
                    logger.debug(f"🔄 Aucune nouvelle update ({consecutive_no_changes}/{max_consecutive_no_changes})")
                
                # ✅ PROTECTION CONTRE LA BOUCLE INFINIE
                if consecutive_no_changes >= max_consecutive_no_changes:
                    logger.warning(f"⚠️ Aucune activité détectée depuis {consecutive_no_changes * check_interval / 60:.1f} minutes")
                    
                    # Vérifier s'il y a eu une réponse qu'on aurait ratée
                    created_at_str = validation_data.get("timestamp") or validation_data.get("created_at")
                    if created_at_str:
                        try:
                            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        except Exception as e:
                            logger.warning(f"⚠️ Erreur parsing timestamp {created_at_str}: {e}")
                            created_at = datetime.now()
                    else:
                        created_at = datetime.now()
                    final_check = self._find_human_reply(update_id, recent_updates, created_at)
                    if final_check:
                        logger.info("🔍 Reply trouvée lors de la vérification finale")
                        validation_context = self._prepare_analysis_context(validation_data)
                        response = await self._parse_human_reply(final_check, update_id, validation_context)
                        
                        self.pending_validations[update_id]["status"] = response.status.value
                        self.pending_validations[update_id]["response"] = response
                        
                        return response
                    else:
                        # Pas de reply trouvée - timeout anticipé
                        logger.warning(f"🔚 Timeout anticipé - aucune activité depuis {consecutive_no_changes * check_interval} secondes")
                        break
                
                # Attendre avant la prochaine vérification
                await asyncio.sleep(check_interval)
                elapsed += check_interval
                
                # Log de progression (seulement toutes les minutes)
                if elapsed % 60 == 0:
                    logger.info(f"⏳ Attente reply validation: {elapsed//60}min/{timeout_minutes}min")
                    
            except Exception as e:
                logger.error(f"❌ Erreur lors de la vérification des replies: {e}")
                consecutive_no_changes += 1
                
                # Si trop d'erreurs consécutives, arrêter
                if consecutive_no_changes >= max_consecutive_no_changes:
                    logger.error("❌ Trop d'erreurs consécutives - arrêt de la surveillance")
                    break
                
                await asyncio.sleep(check_interval)
                elapsed += check_interval
        
        # Timeout ou arrêt anticipé
        reason = "timeout" if elapsed >= timeout_seconds else "no_activity"
        logger.warning(f"⏰ Validation humaine arrêtée: {reason} pour update {update_id}")
        
        # Marquer comme expiré
        self.pending_validations[update_id]["status"] = "expired"
        
        return HumanValidationResponse(
            validation_id=update_id or f"validation_{int(time.time())}_{id(self)}",
            status=HumanValidationStatus.EXPIRED,
            comments=f"Timeout ({reason}) - Aucune réponse humaine reçue dans les {timeout_minutes} minutes",
            validated_by="system",
            should_merge=False,
            should_continue_workflow=False
        )
    
    def _generate_validation_update(self, workflow_results: Dict[str, Any]) -> str:
        """Génère le message d'update pour la validation."""
        
        # Extraire les informations importantes
        task_title = workflow_results.get("task_title", "Tâche")
        success_level = workflow_results.get("success_level", "unknown")
        pr_url = workflow_results.get("pr_url")
        test_results = workflow_results.get("test_results", {})
        error_logs = workflow_results.get("error_logs", [])
        ai_messages = workflow_results.get("ai_messages", [])  # ✅ AJOUT: Récupérer les messages IA
        
        # Header basé sur le succès
        if success_level == "success":
            header = "🤖 **WORKFLOW TERMINÉ - VALIDATION REQUISE** ✅"
        elif success_level == "partial":
            header = "🤖 **WORKFLOW TERMINÉ - VALIDATION REQUISE** ⚠️"
        else:
            header = "🤖 **WORKFLOW TERMINÉ - VALIDATION REQUISE** ❌"
        
        message = f"{header}\n\n"
        message += f"**Tâche**: {task_title}\n\n"
        
        # ✅ AJOUT: Inclure les messages IA du workflow
        if ai_messages:
            message += "📝 **Progression du workflow**:\n"
            # Prendre les 5 derniers messages les plus importants
            important_messages = [msg for msg in ai_messages if "✅" in msg or "❌" in msg or "🚀" in msg or "💻" in msg][-5:]
            if not important_messages:
                important_messages = ai_messages[-3:]  # Fallback aux 3 derniers
            
            for ai_msg in important_messages:
                if ai_msg.strip():  # Éviter les messages vides
                    message += f"• {ai_msg}\n"
            message += "\n"
        
        # Résultats des tests
        if test_results:
            # ✅ CORRECTION: Gérer le cas où test_results est une liste
            if isinstance(test_results, list):
                # Si c'est une liste, prendre le dernier test ou analyser tous
                if test_results:
                    last_test = test_results[-1] if isinstance(test_results[-1], dict) else {}
                    # Analyser les résultats de la liste
                    total_passed = sum(1 for test in test_results if isinstance(test, dict) and test.get("success", False))
                    total_failed = len(test_results) - total_passed
                    
                    if total_failed == 0 and total_passed > 0:
                        message += f"✅ **Tests**: {total_passed} test(s) passent\n"
                    else:
                        message += f"❌ **Tests**: {total_failed} test(s) échoué(s), {total_passed} passent\n"
                else:
                    message += "⚠️ **Tests**: Liste vide\n"
            elif isinstance(test_results, dict):
                # Gestion normale pour les dictionnaires
                if test_results.get("success"):
                    message += "✅ **Tests**: Tous les tests passent\n"
                else:
                    failed_count = len(test_results.get("failed_tests", []))
                    message += f"❌ **Tests**: {failed_count} test(s) échoué(s)\n"
            else:
                message += f"⚠️ **Tests**: Format inattendu ({type(test_results).__name__})\n"
        else:
            message += "⚠️ **Tests**: Aucun test exécuté\n"
        
        # Pull Request
        if pr_url:
            message += f"🔗 **Pull Request**: {pr_url}\n"
        else:
            message += "❌ **Pull Request**: Non créée\n"
        
        # Erreurs si présentes
        if error_logs:
            message += "\n**⚠️ Erreurs rencontrées**:\n"
            for error in error_logs[-3:]:  # Dernières 3 erreurs
                message += f"- {error}\n"
        
        # Instructions de validation
        message += "\n" + "="*50 + "\n"
        message += "**🤝 VALIDATION HUMAINE REQUISE**\n\n"
        message += "**Répondez à cette update avec**:\n"
        message += "• **'oui'** ou **'valide'** → Merge automatique\n"
        message += "• **'non'** ou **'debug'** → Debug avec LLM OpenAI\n\n"
        message += "⏰ *Timeout: 10 minutes*"
        
        return message
    
    async def _get_item_updates(self, item_id: str) -> List[Dict[str, Any]]:
        """Récupère les updates d'un item Monday.com."""
        try:
            result = await self.monday_tool.execute_action(
                action="get_item_updates",
                item_id=item_id
            )
            
            # ✅ PROTECTION RENFORCÉE: Vérifier que result est un dictionnaire  
            if not isinstance(result, dict):
                logger.error(f"❌ Résultat get_updates invalide (type {type(result)}): {result}")
                # Si c'est une liste, c'est probablement une liste d'erreurs GraphQL
                if isinstance(result, list):
                    error_messages = []
                    for error_item in result:
                        if isinstance(error_item, dict):
                            error_messages.append(error_item.get('message', 'Erreur GraphQL inconnue'))
                        else:
                            error_messages.append(str(error_item))
                    error_str = "; ".join(error_messages) if error_messages else str(result)
                    logger.error(f"❌ API Monday a retourné une liste d'erreurs: {error_str}")
                return []
                
            if isinstance(result, dict) and result.get("success", True): # Renforcer la protection
                return result.get("updates", [])
            else:
                logger.error(f"❌ Impossible de récupérer updates item {item_id}: {result}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération updates: {e}")
            return []
    
    def _find_human_reply(self, original_update_id: str, updates: List[Dict[str, Any]], since: datetime) -> Optional[Dict[str, Any]]:
        """Trouve une reply humaine à notre update de validation."""
        
        # ✅ PROTECTION: Vérifier que updates est une liste
        if not isinstance(updates, list):
            logger.warning(f"⚠️ Updates n'est pas une liste (type {type(updates)}), conversion en liste vide")
            updates = []
        
        # ✅ CORRECTION TIMEZONE: S'assurer que 'since' a une timezone pour la comparaison
        from datetime import timezone
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        
        # ✅ CORRECTION CRITIQUE: Trouver le timestamp réel de l'update de validation
        # au lieu d'utiliser 'since' qui peut être incorrect
        validation_update_timestamp = None
        for update in updates:
            if str(update.get("id")) == str(original_update_id):
                timestamp_str = update.get("created_at")
                if timestamp_str:
                    try:
                        validation_update_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        logger.info(f"📅 Timestamp de l'update de validation trouvé: {validation_update_timestamp.isoformat()}")
                        break
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur parsing timestamp update validation: {e}")
        
        # Si on a trouvé le timestamp réel, l'utiliser; sinon utiliser 'since' fourni
        reference_time = validation_update_timestamp if validation_update_timestamp else since
        logger.info(f"🕐 Timestamp de référence pour recherche: {reference_time.isoformat()}")
        
        # ✅ AMÉLIORATION: Recherche en plusieurs passes pour être plus robuste
        candidate_replies = []
        
        logger.info(f"🔍 Recherche de reply parmi {len(updates)} updates pour update_id={original_update_id}")
        logger.info(f"🕐 Recherche des updates créées après: {reference_time.isoformat()}")
        
        for idx, update in enumerate(updates):
            # Protection: vérifier que update est un dictionnaire
            if not isinstance(update, dict):
                logger.debug(f"⚠️ Update {idx} n'est pas un dict: {type(update)}")
                continue
            
            # ✅ CORRECTION CRITIQUE: Exclure l'update de validation originale elle-même
            # pour éviter les faux positifs (le message contient "VALIDATION REQUISE")
            update_id = update.get("id")
            if str(update_id) == str(original_update_id):
                logger.debug(f"⏭️ Ignorer l'update de validation originale (ID: {update_id})")
                continue
                
            # Vérifier si c'est une reply récente
            update_time_str = update.get("created_at")
            if not update_time_str:
                logger.debug(f"⚠️ Update {idx} sans timestamp")
                continue
            
            try:
                update_time = datetime.fromisoformat(update_time_str.replace('Z', '+00:00'))
                # ✅ CORRECTION CRITIQUE: Accepter les updates même légèrement avant l'heure de création
                # pour gérer les délais de synchronisation (marge de 30 secondes)
                time_threshold = reference_time - timedelta(seconds=30)
                if update_time <= time_threshold:
                    logger.debug(f"⏭️ Update {idx} trop ancien ({update_time_str} <= {time_threshold.isoformat()})")
                    continue  # Trop ancien
            except Exception as e:
                logger.warning(f"⚠️ Erreur parsing timestamp {update_time_str}: {e}")
                continue
            
            body = update.get("body", "").strip()
            reply_to_id = update.get("reply_to_id") or update.get("parent_id")
            update_type = update.get("type", "update")
            
            # ✅ AMÉLIORATION: Log plus détaillé pour chaque update récent
            logger.info(f"📝 Update {idx}: id={update_id}, type={update_type}, reply_to={reply_to_id}, créé={update_time_str}, body='{body[:50]}'...")
            
            if not body:
                continue
            
            # ✅ PASSE 1: Replies directes avec reply_to_id (priorité maximale)
            # ✅ CORRECTION CRITIQUE: Comparer les IDs en normalisant les types (string vs int)
            ids_match = False
            if reply_to_id is not None:
                try:
                    # Normaliser les deux en string pour la comparaison
                    reply_to_id_str = str(reply_to_id).strip()
                    original_id_str = str(original_update_id).strip()
                    ids_match = reply_to_id_str == original_id_str
                    
                    if ids_match:
                        logger.info(f"🔍 ID match trouvé: reply_to_id={reply_to_id_str}, original={original_id_str}")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur comparaison IDs: {e}")
            
            if ids_match and self._is_validation_reply(body):
                logger.info(f"💬 Reply directe trouvée: '{body[:50]}'")
                return update
            elif ids_match:
                # Reply directe mais pas un mot-clé clair - garder comme candidat prioritaire
                candidate_replies.append(("direct_reply", update, body))
            
            # ✅ PASSE 2: Updates récentes qui mentionnent des mots-clés de validation
            # (haute priorité même sans reply_to_id si le contenu est clair)
            elif self._is_validation_reply(body):
                # Vérifier si c'est une reply (type="reply") pour priorité plus élevée
                if update_type == "reply":
                    logger.info(f"💬 Reply avec mot-clé de validation trouvée: '{body[:50]}'")
                    candidate_replies.append(("reply_with_keyword", update, body))
                else:
                    candidate_replies.append(("validation_keywords", update, body))
            
            # ✅ PASSE 3: Updates récentes avec des patterns de réponse
            elif self._looks_like_validation_response(body):
                if update_type == "reply":
                    candidate_replies.append(("reply_pattern", update, body))
                else:
                    candidate_replies.append(("response_pattern", update, body))
        
        # ✅ SÉLECTION: Prendre la meilleure réponse par ordre de priorité
        if candidate_replies:
            # Trier par priorité: direct_reply > reply_with_keyword > reply_pattern > validation_keywords > response_pattern
            priority_order = {
                "direct_reply": 1, 
                "reply_with_keyword": 2, 
                "reply_pattern": 3,
                "validation_keywords": 4, 
                "response_pattern": 5
            }
            candidate_replies.sort(key=lambda x: priority_order.get(x[0], 99))
            
            best_match = candidate_replies[0]
            logger.info(f"💬 Meilleure reply trouvée ({best_match[0]}): '{best_match[2][:50]}'")
            return best_match[1]
        
        logger.warning(f"⚠️ Aucune reply valide trouvée parmi {len(updates)} updates")
        return None
    
    def _looks_like_validation_response(self, text: str) -> bool:
        """Vérifie si un texte ressemble à une réponse de validation."""
        import re
        
        # Nettoyer le texte
        cleaned = re.sub(r'<[^>]+>', '', text).strip().lower()
        
        # Patterns qui suggèrent une réponse de validation
        response_patterns = [
            r'\b(je valide|je confirme|c\'est bon|ça marche)\b',
            r'\b(je refuse|je rejette|il faut corriger)\b',
            r'\b(approuvé|validé|refusé|rejeté)\b',
            r'^\s*(ok|non)\s*[.!]*\s*$',  # Réponses très courtes
            r'\b(merge|deploie?|ship)\b',
            r'\b(debug|corrige|fix)\b'
        ]
        
        for pattern in response_patterns:
            if re.search(pattern, cleaned, re.IGNORECASE):
                return True
        
        return False
    
    def _is_validation_reply(self, reply_text: str) -> bool:
        """Vérifie si un texte est une réponse de validation valide."""
        # ✅ CORRECTION: Nettoyer le texte des caractères invisibles et HTML
        import re
        
        if not reply_text:
            return False
        
        # Supprimer BOM et autres caractères invisibles
        cleaned_text = reply_text.replace('\ufeff', '').replace('\u200b', '').replace('\u00a0', '').replace('\xa0', ' ')
        
        # Supprimer les tags HTML basiques et markdown
        cleaned_text = re.sub(r'<[^>]+>', '', cleaned_text)
        cleaned_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned_text)  # Supprimer **bold**
        cleaned_text = cleaned_text.strip().lower()
        
        logger.debug(f"🔍 Vérification texte validation: '{cleaned_text}'")
        
        # ✅ AMÉLIORATION: Détecter les réponses très courtes et simples en premier
        if cleaned_text in ['oui', 'yes', 'ok', 'non', 'no', 'y', 'n', 'o', 'valide', 'approve', 'reject']:
            logger.info(f"✅ Réponse courte détectée: '{cleaned_text}'")
            return True
        
        # Mots-clés pour approbation (patterns larges)
        approval_patterns = [
            r'\b(oui|yes|ok|valide?|approve?d?|accept|go|lgtm)\b',
            r'\b(merge|ship|deploy|good|perfect|correct)\b',
            r'^\s*[✅✓]\s*',
            r'looks?\s+good',
            r"c['']?est\s+bon",  # ✅ CORRECTION: Utiliser guillemets doubles pour la string
            r'je\s+valide'
        ]
        
        # Mots-clés pour rejet/debug
        rejection_patterns = [
            r'\b(non|no|debug|fix|reject|refuse|nope)\b',
            r'\b(probl[eè]me?s?|issue|error|bug|erreur)\b',
            r'^\s*[❌✗]\s*',
            r'ne\s+marche\s+pas',
            r'pas\s+(bon|ok|valide)'
        ]
        
        # Vérifier les patterns d'approbation
        for pattern in approval_patterns:
            if re.search(pattern, cleaned_text, re.IGNORECASE):
                logger.info(f"✅ Pattern d'approbation trouvé: {pattern} dans '{cleaned_text}'")
                return True
        
        # Vérifier les patterns de rejet
        for pattern in rejection_patterns:
            if re.search(pattern, cleaned_text, re.IGNORECASE):
                logger.info(f"✅ Pattern de rejet trouvé: {pattern} dans '{cleaned_text}'")
                return True
        
        logger.debug(f"❌ Aucun pattern de validation trouvé dans: '{cleaned_text}'")
        return False
    
    async def _parse_human_reply(self, reply: Dict[str, Any], validation_id: str, context: Optional[Dict[str, Any]] = None) -> HumanValidationResponse:
        """Parse une réponse humaine avec analyse intelligente."""
        
        # Protection: vérifier que reply est un dictionnaire
        if not isinstance(reply, dict):
            logger.error(f"❌ Reply invalide (type {type(reply)}): {reply}")
            return HumanValidationResponse(
                validation_id=validation_id or f"validation_{int(time.time())}_{id(self)}",
                status=HumanValidationStatus.REJECTED,  # ✅ CORRECTION: ERROR n'existe pas, utiliser REJECTED
                comments="Reply invalide - erreur système",
                validated_by="system",
                should_merge=False,
                should_continue_workflow=False
            )
        
        body = reply.get("body", "").strip()
        # Protection: vérifier que creator est un dictionnaire avant d'appliquer .get()
        creator = reply.get("creator", {})
        if isinstance(creator, dict):
            author = creator.get("name", "Humain")
        else:
            author = "Humain"
        
        logger.info(f"🧠 Analyse intelligente de la réponse: '{body[:50]}...'")
        
        try:
            # Utiliser l'analyseur intelligent hybride
            decision = await intelligent_reply_analyzer.analyze_human_intention(
                reply_text=body,
                context=context
            )
            
            logger.info(f"🎯 Décision intelligente: {decision.decision.value} (confiance: {decision.confidence:.2f})")
            
            # Mapper les intentions vers les statuts de validation
            if decision.decision == IntentionType.APPROVE:
                status = HumanValidationStatus.APPROVED
                should_merge = True
            elif decision.decision == IntentionType.REJECT:
                status = HumanValidationStatus.REJECTED
                should_merge = False
            elif decision.decision == IntentionType.CLARIFICATION_NEEDED:
                # Cas spécial: demander clarification
                logger.warning("⚠️ Clarification requise - marquer comme rejeté temporairement")
                status = HumanValidationStatus.REJECTED
                should_merge = False
            else:  # QUESTION ou UNCLEAR
                # Par défaut, considérer comme rejet pour sécurité
                logger.warning("⚠️ Intention unclear/question - traiter comme rejet par sécurité")
                status = HumanValidationStatus.REJECTED
                should_merge = False
            
            # Enrichir les commentaires avec l'analyse
            enriched_comments = f"{body}"
            if decision.specific_concerns:
                enriched_comments += f"\n\n[IA] Préoccupations détectées: {', '.join(decision.specific_concerns)}"
            if decision.confidence < 0.7:
                enriched_comments += f"\n[IA] Confiance faible ({decision.confidence:.2f}) - Vérification recommandée"
            
            # ✅ CORRECTION CRITIQUE: Utiliser le validation_id de la base de données, pas l'update_id Monday
            db_validation_id = context.get("validation_id") if context else None
            if not db_validation_id:
                # Fallback: chercher dans pending_validations
                pending_validation = self.pending_validations.get(validation_id, {})
                db_validation_id = pending_validation.get("validation_id", validation_id)
            
            return HumanValidationResponse(
                validation_id=db_validation_id or validation_id or f"validation_{int(time.time())}_{id(self)}",
                status=status,
                comments=enriched_comments,
                validated_by=author,
                should_merge=should_merge,
                should_continue_workflow=True,
                # Ajouter les métadonnées de l'analyse intelligente
                analysis_confidence=decision.confidence,
                analysis_method=decision.analysis_method,
                specific_concerns=decision.specific_concerns,
                suggested_action=decision.suggested_action,
                requires_clarification=decision.requires_clarification
            )
            
        except Exception as e:
            logger.error(f"❌ Erreur analyse intelligente: {e}")
            
            # Fallback sur analyse simple
            logger.info("🔄 Fallback vers analyse simple")
            is_approval = self._is_approval_reply(body)
            
            return HumanValidationResponse(
                validation_id=validation_id or f"validation_{int(time.time())}_{id(self)}",
                status=HumanValidationStatus.APPROVED if is_approval else HumanValidationStatus.REJECTED,
                comments=f"{body}\n\n[IA] Analyse simple utilisée (erreur système)",
                validated_by=author,
                should_merge=is_approval,
                should_continue_workflow=True,
                analysis_confidence=0.6,  # Confiance moyenne pour fallback
                analysis_method="simple_fallback_after_error"
            )
    
    def _is_approval_reply(self, reply_text: str) -> bool:
        """Détermine si une réponse est une approbation."""
        # Patterns d'approbation
        approval_patterns = [
            r'\b(oui|yes|ok|valide?|approve?d?|accept|go)\b',
            r'\b(merge|ship|deploy|good|perfect)\b',
            r'^\s*[✅✓]\s*$',
            r'lgtm|looks good'
        ]
        
        for pattern in approval_patterns:
            if re.search(pattern, reply_text, re.IGNORECASE):
                return True
        
        return False
    
    def _prepare_analysis_context(self, validation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prépare le contexte pour l'analyse intelligente des réponses."""
        
        workflow_results = validation_data.get("workflow_results", {})
        
        context = {
            "task_title": workflow_results.get("task_title"),
            "task_id": workflow_results.get("task_id"),
            "task_type": "development",  # Ou extraire du workflow
            # ✅ CORRECTION: Protection contre 'list' object has no attribute 'get'
            "tests_passed": self._safe_get_test_success(workflow_results.get("test_results")),
            "pr_url": workflow_results.get("pr_url"),
            "error_count": len(workflow_results.get("error_logs", [])),
            "success_level": workflow_results.get("success_level", "unknown"),
            "urgent": False,  # Pourrait être extrait des métadonnées de tâche
            "created_at": validation_data.get("timestamp") or validation_data.get("created_at"),
            "workflow_duration": self._calculate_workflow_duration(validation_data),
            "validation_id": validation_data.get("validation_id")  # ✅ NOUVEAU: Inclure validation_id pour les réponses DB
        }
        
        return context
    
    def _calculate_workflow_duration(self, validation_data: Dict[str, Any]) -> Optional[int]:
        """Calcule la durée du workflow en minutes."""
        try:
            created_at_str = validation_data.get("timestamp") or validation_data.get("created_at")
            if created_at_str:
                if isinstance(created_at_str, str):
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                else:
                    created_at = created_at_str
                # ✅ CORRECTION: S'assurer que les datetimes ont le même timezone
                from datetime import timezone
                now_utc = datetime.now(timezone.utc)
                # Si created_at est offset-naive, le rendre offset-aware
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                duration = (now_utc - created_at).total_seconds() / 60
                return int(duration)
        except Exception:
            pass
        return None
    
    def cleanup_completed_validations(self, older_than_hours: int = 24):
        """Nettoie les validations terminées anciennes."""
        # ✅ CORRECTION: Utiliser datetime avec timezone
        from datetime import timezone
        cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        
        to_remove = []
        for update_id, validation in self.pending_validations.items():
            validation_time_str = validation.get("timestamp") or validation.get("created_at")
            if validation_time_str:
                try:
                    if isinstance(validation_time_str, str):
                        validation_time = datetime.fromisoformat(validation_time_str.replace('Z', '+00:00'))
                    else:
                        validation_time = validation_time_str
                    if validation_time < cutoff and validation.get("status") != "pending":
                        to_remove.append(update_id)
                except Exception as e:
                    logger.warning(f"⚠️ Erreur parsing timestamp pour cleanup: {e}")
                    # En cas d'erreur, considérer comme ancien et nettoyer
                    if validation.get("status") != "pending":
                        to_remove.append(update_id)
        
        for update_id in to_remove:
            del self.pending_validations[update_id]
        
        if to_remove:
            logger.info(f"🧹 Nettoyage: {len(to_remove)} validations supprimées")
    
    async def _recover_validation_context(self, update_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère le contexte de validation depuis Monday.com quand pending_validations est vide.
        
        Args:
            update_id: ID de l'update de validation
            
        Returns:
            Dictionnaire de validation reconstitué ou None si impossible
        """
        try:
            logger.info(f"🔄 Tentative de récupération du contexte pour update {update_id}")
            
            # Stratégie 1: Extraire l'item_id depuis l'update_id si c'est un format généré
            item_id = None
            
            # Format: success_update_{item_id} ou failed_update_{item_id}
            if "_update_" in update_id:
                item_id = update_id.split("_update_")[-1]
                logger.info(f"📋 Item ID extrait de update_id: {item_id}")
            else:
                # Stratégie 2: C'est probablement un vrai ID Monday.com
                # Utiliser l'item_id du contexte d'exécution actuel ou des logs récents
                logger.info(f"🔍 Update ID Monday.com détecté: {update_id}")
                
                # Essayer de trouver l'item_id dans les logs récents ou le contexte Celery
                # Pour l'instant, utilisons l'item_id connu depuis les logs
                # TODO: Améliorer avec une recherche dans les logs Celery ou base de données
                
                # Méthode de fallback: utiliser l'item_id connu depuis les logs récents
                potential_item_ids = ["5010569330"]  # À remplacer par une recherche dynamique
                
                for potential_item_id in potential_item_ids:
                    logger.info(f"🔍 Test avec item_id potentiel: {potential_item_id}")
                    
                    # Vérifier si cet item contient notre update
                    updates_result = await self.monday_tool.execute_action(
                        action="get_item_updates",
                        item_id=potential_item_id
                    )
                    
                    if updates_result.get("success", False):
                        updates = updates_result.get("updates", [])
                        
                        # Chercher notre update dans cet item
                        for update in updates:
                            if str(update.get("id")) == str(update_id):
                                logger.info(f"✅ Update {update_id} trouvée dans item {potential_item_id}")
                                item_id = potential_item_id
                                break
                        
                        if item_id:
                            break
                
                if not item_id:
                    logger.error(f"❌ Impossible de trouver l'item_id pour update {update_id}")
                    return None
            
            if not item_id:
                logger.error(f"❌ Impossible d'extraire item_id de {update_id}")
                return None
            
            # Récupérer les updates de l'item pour trouver notre update de validation
            updates_result = await self.monday_tool.execute_action(
                action="get_item_updates",
                item_id=item_id
            )
            
            if not updates_result.get("success", False):
                logger.error(f"❌ Erreur récupération updates pour item {item_id}: {updates_result.get('error')}")
                return None
            
            updates = updates_result.get("updates", [])
            
            # Chercher notre update de validation
            target_update = None
            for update in updates:
                if str(update.get("id")) == str(update_id):
                    target_update = update
                    break
            
            if not target_update:
                logger.warning(f"⚠️ Update {update_id} non trouvée dans les updates de l'item {item_id}")
                # Créer un contexte de base pour permettre la validation
                return {
                    "item_id": item_id,
                    "message": "Contexte récupéré - validation en cours",
                    "timestamp": datetime.now().isoformat(),
                    "fallback_mode": True,
                    "recovered": True
                }
            
            # Reconstituer le contexte de validation
            recovery_context = {
                "item_id": item_id,
                "message": target_update.get("body", "Message de validation"),
                "timestamp": target_update.get("created_at", datetime.now().isoformat()),
                "fallback_mode": False,
                "recovered": True,
                "original_creator": target_update.get("creator", {}).get("name", "Unknown")
            }
            
            logger.info(f"✅ Contexte reconstitué pour update {update_id}")
            return recovery_context
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération du contexte: {e}")
            return None


# Instance globale
monday_validation_service = MondayValidationService() 