"""Service de réception et traitement des webhooks Monday.com."""

import hashlib
import hmac
import json
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
import time

from models.schemas import TaskRequest, WebhookPayload
from tools.monday_tool import MondayTool
# from graph.workflow_graph import run_workflow  # ✅ Retiré - on utilise Celery maintenant
from utils.logger import get_logger
from config.settings import get_settings
from admin.backend.database import get_db_connection
from utils.github_parser import enrich_task_with_description_info

logger = get_logger(__name__)

class WebhookService:
    """Service de gestion des webhooks Monday.com."""

    def __init__(self):
        self.settings = get_settings()
        self.monday_tool = MondayTool()

        # ✅ NOUVEAU: Cache pour déduplication des webhooks
        self._webhook_cache = {}
        self._cache_expiry = 300  # 5 minutes
        self._processing_locks = {}  # Verrous pour éviter le traitement parallèle

    async def process_webhook(self, payload: Dict[str, Any], signature: Optional[str] = None) -> Dict[str, Any]:
        """
        Traite un webhook Monday.com avec déduplication renforcée.
        """
        try:
            # ✅ NOUVEAU: Créer une signature unique du webhook
            webhook_signature = self._create_webhook_signature(payload)

            # ✅ NOUVEAU: Vérifier si ce webhook est déjà en cours de traitement
            current_time = time.time()

            # Nettoyer le cache expiré
            self._cleanup_webhook_cache(current_time)

            # Vérifier si ce webhook a déjà été traité récemment
            if webhook_signature in self._webhook_cache:
                cached_data = self._webhook_cache[webhook_signature]
                logger.warning(f"🚫 Webhook déjà traité il y a {current_time - cached_data['timestamp']:.1f}s")
                logger.warning(f"   Signature: {webhook_signature}")
                logger.warning(f"   Task ID: {cached_data.get('task_id', 'unknown')}")
                return {
                    "success": True,
                    "task_id": cached_data.get('task_id'),
                    "task_exists": True,
                    "message": "Webhook déjà traité (déduplication)",
                    "deduplicated": True
                }

            # ✅ NOUVEAU: Acquérir un verrou pour ce webhook
            if webhook_signature in self._processing_locks:
                logger.warning(f"🔒 Webhook en cours de traitement - attente...")
                # Attendre maximum 30 secondes
                for _ in range(30):
                    await asyncio.sleep(1)
                    if webhook_signature not in self._processing_locks:
                        break
                else:
                    logger.error(f"❌ Timeout - webhook toujours en cours de traitement")
                    return {
                        "success": False,
                        "error": "Webhook timeout - traitement parallèle détecté"
                    }

            # Marquer comme en cours de traitement
            self._processing_locks[webhook_signature] = current_time

            try:
                # Marquer dans le cache immédiatement
                self._webhook_cache[webhook_signature] = {
                    "timestamp": current_time,
                    "status": "processing"
                }

                logger.info("📨 Réception d'un webhook Monday.com")

                # 1. Sauvegarder le webhook en base
                webhook_id = await self._save_webhook_event(payload, signature)

                # 2. Valider la signature si fournie
                if signature and not self._validate_signature(payload, signature):
                    logger.warning("❌ Signature webhook invalide")
                    await self._update_webhook_status(webhook_id, 'failed', 'Signature invalide')
                    return {
                        "success": False,
                        "error": "Signature webhook invalide",
                        "status_code": 401
                    }

                # 3. Parser le payload
                webhook_data = WebhookPayload(**payload)

                # 4. Vérifier si c'est un challenge de validation
                if webhook_data.challenge:
                    logger.info("✅ Challenge webhook reçu")
                    await self._update_webhook_status(webhook_id, 'processed')
                    return {
                        "success": True,
                        "challenge": webhook_data.challenge,
                        "status_code": 200
                    }

                # 5. Traiter l'événement
                if not webhook_data.event:
                    logger.warning("⚠️ Webhook sans événement")
                    await self._update_webhook_status(webhook_id, 'ignored', 'Aucun événement')
                    return {
                        "success": False,
                        "error": "Aucun événement dans le webhook",
                        "status_code": 400
                    }

                # 6. Vérifier les webhooks en doublon (protection contre les multiples envois Monday.com)
                duplicate_check = await self._check_duplicate_webhook(payload)
                if duplicate_check:
                    logger.warning("⚠️ Webhook en doublon détecté:")
                    logger.warning(f"   Webhook similaire traité: {duplicate_check['webhook_events_id']} à {duplicate_check['processed_at']}")
                    logger.warning("   🛑 Webhook ignoré pour éviter la duplication")
                    await self._update_webhook_status(webhook_id, 'processed', 'Doublon ignoré')
                    return {
                        "success": True,
                        "message": "Webhook doublon ignoré",
                        "status_code": 200
                    }

                # 7. Extraire les informations de la tâche
                task_info = self.monday_tool.parse_monday_webhook(payload)

                if not task_info:
                    logger.info("ℹ️ Webhook ignoré - pas pertinent pour notre workflow")
                    await self._update_webhook_status(webhook_id, 'ignored', 'Pas pertinent')
                    return {
                        "success": True,
                        "message": "Webhook ignoré",
                        "status_code": 200
                    }

                # 7. Créer une requête de tâche
                task_request = await self._create_task_request(task_info)

                if not task_request:
                    logger.warning("❌ Impossible de créer la requête de tâche")
                    await self._update_webhook_status(webhook_id, 'failed', 'Impossible de créer la requête')
                    return {
                        "success": False,
                        "error": "Impossible de créer la requête de tâche",
                        "status_code": 400
                    }

                # 8. Sauvegarder la tâche en base
                task_id = await self._save_task(task_request)

                # 9. Sauvegarder le run en base
                run_id = await self._save_task_run(task_id, task_request)

                # Note : Le statut de la tâche est automatiquement mis à jour par le trigger sync_task_status

                # 10. Mettre à jour le webhook avec la tâche liée
                await self._update_webhook_status(webhook_id, 'processed', related_task_id=task_id)

                # 11. ✅ CORRECTION: Ne plus lancer le workflow ici pour éviter la duplication
                # Le workflow est déjà lancé par main.py via process_monday_webhook
                logger.info(f"📋 Tâche créée et prête pour workflow: {task_request.title}")

                # Retourner le succès sans lancer un deuxième workflow
                return {
                    "success": True,
                    "message": "Tâche créée avec succès - workflow géré par main.py",
                    "task_id": task_request.task_id,
                    "status": "created",
                    "status_code": 201  # Created
                }

                # ANCIEN CODE SUPPRIMÉ pour éviter le double lancement :
                # - celery_app.send_task("ai_agent_background.execute_workflow")
                # Ce workflow est maintenant géré directement par main.py

            except Exception as wf_err:
                err_msg = str(wf_err)
                logger.error(f"❌ Erreur lors de l'envoi du workflow à Celery: {err_msg}")

                # Mettre à jour le statut de la tâche en échec
                await self._update_task_status(task_id, "failed")

                if "Invalid status transition" in err_msg:
                    logger.warning(f"⚠️ Transition de statut idempotente ignorée: {err_msg}")
                    return {
                        "success": True,
                        "message": "Workflow lancé avec avertissement (transition identique ignorée)",
                        "task_id": task_request.task_id,
                        "warning": err_msg,
                        "status_code": 200
                    }

                # Relancer l'exception pour le gestionnaire global
                raise

            except Exception as e:
                error_msg = f"Erreur lors du traitement du webhook: {str(e)}"
                logger.error(error_msg, exc_info=True)

                # Gestion spéciale pour les transitions de statut identiques
                if "Invalid status transition" in str(e):
                    logger.warning(f"⚠️ Transition de statut identique détectée (webhook traité quand même): {str(e)}")
                    await self._update_webhook_status(webhook_id, 'processed')
                    return {
                        "success": True,
                        "message": "Webhook traité (transition de statut identique ignorée)",
                        "warning": str(e),
                        "status_code": 200
                    }

                await self._update_webhook_status(webhook_id, 'failed', error_msg)

                return {
                    "success": False,
                    "error": error_msg,
                    "status_code": 500
                }
            finally:
                # ✅ NOUVEAU: Libérer le verrou après le traitement
                if webhook_signature in self._processing_locks:
                    del self._processing_locks[webhook_signature]
                    logger.debug(f"🔓 Libération du verrou pour signature: {webhook_signature}")
        except Exception as e:
            logger.error(f"Erreur générale lors du traitement du webhook: {e}", exc_info=True)
            return {"success": False, "error": str(e), "status_code": 500}

    def _create_webhook_signature(self, payload: Dict[str, Any]) -> str:
        """Crée une signature unique pour un webhook."""
        payload_str = json.dumps(payload, sort_keys=True).encode('utf-8')
        return hashlib.sha256(payload_str).hexdigest()

    def _cleanup_webhook_cache(self, current_time: float):
        """Nettoie le cache des webhooks qui ont expiré."""
        expired_keys = [
            k for k, v in self._webhook_cache.items()
            if current_time - v['timestamp'] > self._cache_expiry
        ]
        for key in expired_keys:
            logger.debug(f"🧹 Nettoyage du cache webhook: {key}")
            del self._webhook_cache[key]

    def _validate_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """Valide la signature du webhook Monday.com."""

        try:
            # Monday.com utilise HMAC-SHA256
            payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')

            expected_signature = hmac.new(
                self.settings.webhook_secret.encode('utf-8'),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()

            # Comparer en toute sécurité
            return hmac.compare_digest(signature, expected_signature)

        except Exception as e:
            logger.error(f"Erreur lors de la validation de signature: {e}")
            return False

    async def _save_webhook_event(self, payload: Dict[str, Any], signature: Optional[str] = None) -> int:
        """Sauvegarde le webhook en base de données."""
        try:
            conn = await get_db_connection()
            logger.debug("Connexion DB établie pour sauvegarde webhook")

            result = await conn.fetchrow("""
                INSERT INTO webhook_events (source, event_type, payload, signature, processed, processing_status)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING webhook_events_id
            """,
                'monday',
                payload.get('event', {}).get('type'),
                json.dumps(payload),
                signature,
                False,
                'pending'
            )
            return result['webhook_events_id']
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde webhook en base: {e}")
            # Retourner un ID temporaire pour continuer le traitement
            return -1
        finally:
            if 'conn' in locals():
                await conn.close()

    async def _save_task(self, task_request: TaskRequest) -> int:
        """Sauvegarde la tâche en base de données avec gestion des doublons améliorée."""
        try:
            conn = await get_db_connection()
            logger.debug("Connexion DB établie pour sauvegarde tâche")

            # 1. Vérifier si la tâche existe déjà par monday_item_id
            existing_task = await conn.fetchrow("""
                SELECT tasks_id, internal_status FROM tasks
                WHERE monday_item_id = $1
            """, int(task_request.task_id))

            if existing_task:
                logger.info(f"📋 Tâche existante trouvée par ID: {existing_task['tasks_id']}, statut: {existing_task['internal_status']}")
                return existing_task['tasks_id']

            # 2. Vérifier les doublons par titre + créé dans les 5 dernières minutes
            # (protection contre les webhooks multiples de Monday.com)
            similar_task = await conn.fetchrow("""
                SELECT tasks_id, monday_item_id, internal_status
                FROM tasks
                WHERE title = $1
                AND created_at >= NOW() - INTERVAL '5 minutes'
                AND internal_status IN ('pending', 'processing')
                ORDER BY created_at DESC
                LIMIT 1
            """, task_request.title)

            if similar_task:
                logger.warning("⚠️ Tâche similaire détectée dans les 5 dernières minutes:")
                logger.warning(f"   Existante: ID {similar_task['tasks_id']}, Monday ID {similar_task['monday_item_id']}")
                logger.warning(f"   Nouvelle: Monday ID {task_request.task_id}")
                logger.warning(f"   Titre: {task_request.title}")
                logger.warning("   🛑 Duplication probable détectée - utilisation de la tâche existante")
                return similar_task['tasks_id']

            # Créer une nouvelle tâche
            result = await conn.fetchrow("""
                INSERT INTO tasks (
                    monday_item_id, monday_board_id, title, description, priority,
                    repository_url, repository_name, default_branch, internal_status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING tasks_id
            """,
                int(task_request.task_id),
                None,
                task_request.title,
                task_request.description,
                task_request.priority.value,
                task_request.repository_url or '',
                None,
                task_request.base_branch,
                'pending'  # Statut initial
            )
            logger.info(f"📋 Nouvelle tâche créée: ID {result['tasks_id']}")
            return result['tasks_id']
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde tâche en base: {e}")
            raise
        finally:
            if 'conn' in locals():
                await conn.close()

    async def _save_task_run(self, task_id: int, task_request: TaskRequest) -> int:
        """Sauvegarde le run en base de données avec gestion des doublons."""
        try:
            conn = await get_db_connection()

            # Vérifier s'il y a déjà un run actif pour cette tâche
            existing_run = await conn.fetchrow("""
                SELECT tasks_runs_id, status FROM task_runs
                WHERE task_id = $1 AND status IN ('started', 'running', 'pending')
                ORDER BY started_at DESC
                LIMIT 1
            """, task_id)

            if existing_run:
                logger.info(f"📊 Run existant trouvé: ID {existing_run['tasks_runs_id']}, statut: {existing_run['status']}")
                return existing_run['tasks_runs_id']

            # Créer un nouveau run
            result = await conn.fetchrow("""
                INSERT INTO task_runs (
                    task_id, status, git_branch_name, ai_provider
                ) VALUES ($1, $2, $3, $4)
                RETURNING tasks_runs_id
            """,
                task_id,
                'started',  # Statut 'started' au lieu de 'pending'
                task_request.branch_name,
                'claude'
            )
            logger.info(f"📊 Nouveau run créé: ID {result['tasks_runs_id']}")
            return result['tasks_runs_id']
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde run en base: {e}")
            raise
        finally:
            if 'conn' in locals():
                await conn.close()

    async def _update_task_status(self, task_db_id: int, new_status: str):
        """Met à jour le statut d'une tâche de manière idempotente."""
        try:
            conn = await get_db_connection()

            # Vérifier le statut actuel
            row = await conn.fetchrow("SELECT internal_status FROM tasks WHERE tasks_id=$1", task_db_id)

            if row and row["internal_status"] != new_status:
                await conn.execute(
                    "UPDATE tasks SET internal_status=$1, updated_at=NOW() WHERE tasks_id=$2",
                    new_status, task_db_id
                )
                logger.info(f"📊 Statut tâche {task_db_id} mis à jour: {row['internal_status']} → {new_status}")
            else:
                logger.debug(f"📊 Statut identique pour tâche {task_db_id}: {new_status}")
                # C'est normal - ne pas lever d'exception

        except Exception as e:
            logger.error(f"❌ Erreur mise à jour statut tâche {task_db_id}: {e}")
            # Ne pas relancer l'exception pour éviter de faire échouer le traitement
        finally:
            if 'conn' in locals():
                await conn.close()

    async def _update_webhook_status(self, webhook_id: int, status: str, error_message: Optional[str] = None, related_task_id: Optional[int] = None):
        """Met à jour le statut du webhook."""
        try:
            conn = await get_db_connection()

            await conn.execute("""
                UPDATE webhook_events
                SET processing_status = $1,
                    error_message = $2,
                    related_task_id = $3,
                    processed = $4,
                    processed_at = CASE WHEN $4 THEN NOW() ELSE processed_at END
                WHERE webhook_events_id = $5
            """, status, error_message, related_task_id, status == 'processed', webhook_id)

        except Exception as e:
            logger.error(f"❌ Erreur mise à jour webhook {webhook_id}: {e}")
        finally:
            if 'conn' in locals():
                await conn.close()

    async def _create_task_request(self, task_info: Dict[str, Any]) -> Optional[TaskRequest]:
        """Crée une TaskRequest à partir des informations d'une tâche Monday.com."""

        try:
            item_id = task_info.get("task_id", "")

            # ✅ AMÉLIORATION: Vérification précoce des items de test
            if self._is_test_item(item_id):
                logger.info(f"⚠️ Item de test détecté ({item_id}) - Traitement simplifié")
                return self._create_test_task_request(task_info)

            # Récupérer les informations détaillées de l'item depuis Monday.com
            logger.info(f"📥 Récupération des détails pour l'item Monday.com: {item_id}")

            item_data = await self.monday_tool._get_item_info(item_id)

            if not item_data.get("success"):
                error_msg = item_data.get("error", "Erreur inconnue")
                logger.error(f"❌ Impossible de récupérer les détails de l'item {item_id}: {error_msg}")

                # ✅ AMÉLIORATION: Gestion différentielle selon le type d'erreur
                if "non trouvé" in error_msg or "supprimé" in error_msg:
                    # L'item a probablement été supprimé entre l'envoi du webhook et le traitement
                    logger.warning(f"⚠️ Item {item_id} supprimé après envoi du webhook - Ceci peut arriver lors de suppressions rapides")
                    # Créer une tâche minimale pour éviter l'arrêt complet du workflow
                    return self._create_fallback_task_request(task_info, f"Item supprimé: {error_msg}")
                else:
                    # Autres erreurs (permissions, API down, etc.)
                    raise ValueError(f"Item Monday.com {item_id} inaccessible: {error_msg}")

            # Extraire les informations nécessaires
            title = item_data.get("name", task_info.get("title", "Tâche sans titre"))

            # ✅ AMÉLIORATION: Extraction de description plus robuste
            description = None

            # Fonction helper pour extraire texte sécurisé
            def safe_extract_column_text(column: Dict[str, Any]) -> str:
                """Extrait le texte d'une colonne Monday.com de manière sécurisée."""
                if not isinstance(column, dict):
                    return ""

                # Essayer plusieurs propriétés possibles dans l'ordre de priorité
                text_value = (
                    column.get("text") or
                    column.get("value") or
                    (column.get("display_value") if column.get("display_value") else "") or
                    ""
                ).strip()

                # Si c'est un dict dans value, essayer d'extraire le texte
                if not text_value and isinstance(column.get("value"), dict):
                    value_dict = column.get("value", {})
                    text_value = (
                        value_dict.get("text") or
                        value_dict.get("value") or
                        str(value_dict.get("display_value", ""))
                    ).strip()

                return text_value

            # DEBUG: Afficher toutes les colonnes disponibles
            if "column_values" in item_data:
                # ✅ PROTECTION: Normaliser column_values en liste pour le traitement
                column_values = item_data["column_values"]
                if isinstance(column_values, dict):
                    # Cas normal : l'API Monday.com retourne parfois un dict au lieu d'une liste
                    logger.debug(f"🔧 column_values reçu comme dict, conversion en liste ({len(column_values)} colonnes)")
                    column_values = list(column_values.values())
                elif not isinstance(column_values, list):
                    # Cas anormal : type inattendu
                    logger.warning(f"⚠️ column_values type inattendu: {type(column_values)}, fallback vers liste vide")
                    column_values = []
                # Si c'est déjà une liste, on la garde telle quelle

                column_names = [col.get("id", "no_id") for col in column_values if isinstance(col, dict)]
                logger.info(f"🔍 DEBUG - Colonnes disponibles dans Monday.com: {column_names}")

                # ✅ AMÉLIORATION: Chercher la description avec plus de flexibilité
                description_candidates = []

                for col in column_values:
                    col_id = col.get("id", "").lower()
                    col_title = col.get("title", "").lower()
                    col_text = safe_extract_column_text(col)

                    # Logger les colonnes potentielles pour debug
                    if any(keyword in col_id for keyword in ["desc", "detail", "note", "comment", "text", "sujet"]) or \
                       any(keyword in col_title for keyword in ["desc", "detail", "note", "comment", "text", "sujet"]):
                        logger.info(f"🔍 DEBUG - Colonne potentielle: id='{col.get('id')}', title='{col.get('title')}', text='{col_text[:50]}...'")

                        if col_text and len(col_text) > 10:  # Priorité aux descriptions substantielles
                            description_candidates.append((col_text, len(col_text), col.get("id")))

                # Choisir la meilleure description (la plus longue)
                if description_candidates:
                    description_candidates.sort(key=lambda x: x[1], reverse=True)  # Trier par longueur
                    description = description_candidates[0][0]
                    source_column = description_candidates[0][2]
                    logger.info(f"📝 Description sélectionnée depuis colonne '{source_column}': {description[:100]}...")

            # ✅ FALLBACK 1: Chercher dans les updates/posts de l'item (description récente)
            if not description:
                logger.info("🔍 Recherche de description dans les updates Monday.com...")
                try:
                    # ✅ CORRECTION: Vérifier la configuration Monday.com avant l'appel
                    if not hasattr(self.monday_tool, 'api_token') or not self.monday_tool.api_token:
                        logger.info("💡 Monday.com non configuré - utilisation de description par défaut")
                        description = f"Tâche {task_info.get('task_id', 'N/A')}: {task_info.get('title', 'Développement')}"
                    else:
                        updates_result = await self.monday_tool._arun(
                            action="get_item_updates",
                            item_id=task_info["task_id"]
                        )

                        if updates_result.get("success") and updates_result.get("updates"):
                            # Chercher une update qui contient une description valide
                            for update in updates_result["updates"][:5]:  # Maximum 5 updates récentes
                                update_body = update.get("body", "").strip()
                                if update_body and len(update_body) > 20:  # Description substantielle
                                    # Nettoyer le HTML si présent
                                    import re
                                    clean_body = re.sub(r'<[^>]+>', '', update_body)
                                    if clean_body and len(clean_body) > 20:
                                        description = clean_body
                                        logger.info(f"📝 Description trouvée dans update: {description[:100]}...")
                                        break
                except Exception as e:
                    logger.warning(f"⚠️ Erreur récupération updates: {e}")

            # ✅ FALLBACK 2: Utiliser le titre de la tâche comme description minimale
            if not description and title:
                description = f"Tâche: {title}"
                logger.info(f"📝 Description générée depuis le titre: {description}")

            # ✅ VALIDATION: S'assurer qu'on a au moins quelque chose
            if not description:
                description = "Description non disponible - Veuillez ajouter plus de détails dans Monday.com"
                logger.warning("⚠️ Aucune description trouvée dans Monday.com après toutes les tentatives")

            logger.info(f"📄 Description finale: {description[:100]}{'...' if len(description) > 100 else ''}")

            # Rechercher la branche Git
            git_branch = self._extract_column_value(item_data, "branche_git", "text")
            if not git_branch:
                git_branch = self._generate_branch_name(title)

            # Autres informations
            assignee = self._extract_column_value(item_data, "personne", "name")
            priority = self._extract_column_value(item_data, "priorite", "text", "medium")
            repository_url = self._extract_column_value(item_data, "repo_url", "text") or ""

            # Préparer les données de base de la tâche
            base_task_data = {
                "task_id": task_info["task_id"],
                "title": title,
                "description": description,
                "branch_name": git_branch,
                "repository_url": repository_url,
                "priority": priority,
                "assignee": assignee
            }

            # Enrichir avec les informations extraites de la description
            logger.info(f"📝 Analyse de la description pour enrichissement: {description[:100]}...")
            logger.info(f"🔗 URL de base (avant enrichissement): {repository_url}")

            enriched_data = enrich_task_with_description_info(base_task_data, description)

            final_url = enriched_data.get("repository_url", "")
            if final_url != repository_url:
                logger.info(f"🎯 URL GitHub finale (après enrichissement): {final_url}")
            else:
                logger.info(f"📝 URL GitHub finale (inchangée): {final_url}")

            # Validation critique: URL GitHub obligatoire
            if not final_url or not final_url.strip():
                error_msg = "❌ ERREUR CRITIQUE: Aucune URL GitHub trouvée dans la description ni dans les colonnes Monday.com"
                logger.error(error_msg)
                logger.error("💡 SOLUTION: Ajoutez l'URL GitHub dans la description de la tâche Monday.com")
                logger.error("📝 EXEMPLE: 'Implémente login JWT pour: https://github.com/user/repo'")

                raise ValueError(
                    "URL GitHub manquante. "
                    "Veuillez spécifier l'URL GitHub dans la description de la tâche Monday.com. "
                    "Exemple: 'Implémente login pour: https://github.com/user/repo'"
                )

            # ✅ AJOUT: Vérifier la déduplication avant de créer la tâche
            task_id = enriched_data["task_id"]

            # Vérifier si une tâche similaire est déjà en cours
            if hasattr(self, '_active_tasks'):
                if task_id in self._active_tasks:
                    logger.warning(f"⚠️ Tâche {task_id} déjà en cours - ignorer webhook dupliqué")
                    return None
            else:
                self._active_tasks = set()

            # Marquer la tâche comme active
            self._active_tasks.add(task_id)

            # Créer la requête de tâche avec les données enrichies
            task_request = TaskRequest(
                task_id=enriched_data["task_id"],
                title=enriched_data["title"],
                description=enriched_data["description"],
                branch_name=enriched_data["branch_name"],
                repository_url=enriched_data["repository_url"],
                priority=enriched_data["priority"],
                assignee=enriched_data.get("assignee"),
                files_to_modify=enriched_data.get("files_to_modify"),
                created_at=datetime.now()
            )

            logger.info(f"📋 Tâche créée: {task_request.title} (Branche: {task_request.branch_name})")

            # ✅ AJOUT: Programmer le nettoyage de la tâche après un délai
            # Cela évite les fuites mémoire et permet de refaire la tâche plus tard si nécessaire
            import asyncio
            asyncio.create_task(self._cleanup_task_later(task_id, delay_minutes=10))

            return task_request

        except Exception as e:
            logger.error(f"Erreur lors de la création de la requête de tâche: {e}")
            return None

    async def _cleanup_task_later(self, task_id: str, delay_minutes: int = 10):
        """Nettoie une tâche de la liste des tâches actives après un délai."""
        import asyncio
        await asyncio.sleep(delay_minutes * 60)  # Attendre le délai en secondes

        if hasattr(self, '_active_tasks') and task_id in self._active_tasks:
            self._active_tasks.discard(task_id)
            logger.info(f"🧹 Nettoyage tâche {task_id} de la liste des tâches actives")

    def _extract_column_value(self, item_data: Dict[str, Any], column_name: str,
                            value_type: str = "text", default: Any = None) -> Any:
        """Extrait une valeur de colonne Monday.com."""

        try:
            column_values = item_data.get("column_values", [])

            # ✅ PROTECTION: Normaliser column_values en liste
            if isinstance(column_values, dict):
                # Format dict normal de l'API Monday.com
                logger.debug(f"🔧 _extract_column_value: Conversion dict → liste ({len(column_values)} colonnes)")
                column_values = list(column_values.values())
            elif not isinstance(column_values, list):
                # Type inattendu
                logger.warning(f"⚠️ _extract_column_value: Type column_values inattendu: {type(column_values)}")
                column_values = []

            for column in column_values:
                if (column.get("id", "").lower() == column_name.lower() or
                    column_name.lower() in column.get("id", "").lower()):

                    if value_type == "text":
                        return column.get("text", default)
                    elif value_type == "value":
                        return column.get("value", default)
                    elif value_type == "name":
                        value = column.get("value")
                        if value and isinstance(value, dict):
                            return value.get("name", default)
                        return default

            return default

        except Exception as e:
            logger.warning(f"Erreur extraction colonne {column_name}: {e}")
            return default

    def _generate_branch_name(self, title: str) -> str:
        """Génère un nom de branche Git à partir du titre de la tâche."""

        import re

        clean_title = re.sub(r'[^\w\s-]', '', title.lower())
        clean_title = re.sub(r'\s+', '-', clean_title.strip())

        if len(clean_title) > 50:
            clean_title = clean_title[:50].rstrip('-')

        branch_name = f"feature/{clean_title}"
        timestamp = datetime.now().strftime("%m%d")
        branch_name += f"-{timestamp}"

        return branch_name

    def _is_test_item(self, item_id: str) -> bool:
        """Vérifie si l'item est un item de test (par exemple, un item avec un ID spécifique)."""
        # Ajoutez ici les conditions pour détecter les items de test
        # Par exemple, si l'ID de l'item contient "test" ou "sandbox"
        return "test" in item_id.lower() or "sandbox" in item_id.lower()

    def _create_test_task_request(self, task_info: Dict[str, Any]) -> Optional[TaskRequest]:
        """Crée une requête de tâche pour un item de test."""
        logger.warning(f"🧪 Création d'une requête de tâche pour un item de test: {task_info.get('item_id')}")

        title = f"Test Task - {task_info.get('item_id', 'N/A')}"
        description = f"This is a test task created for item ID: {task_info.get('item_id', 'N/A')}. Please ignore."
        git_branch = self._generate_branch_name(title)
        repository_url = "" # Pas d'URL GitHub pour les items de test
        priority = "medium"
        assignee = None

        task_request = TaskRequest(
            task_id=task_info["task_id"],
            title=title,
            description=description,
            branch_name=git_branch,
            repository_url=repository_url,
            priority=priority,
            assignee=assignee,
            files_to_modify=[],
            created_at=datetime.now()
        )
        logger.info(f"📋 Requête de tâche de test créée: {task_request.title}")
        return task_request

    def _create_fallback_task_request(self, task_info: Dict[str, Any], error_reason: str) -> TaskRequest:
        """Crée une TaskRequest de fallback pour des items inaccessibles."""

        item_id = task_info.get("task_id", "unknown")
        title = task_info.get("title", f"Tâche {item_id}")

        logger.info(f"🔄 Création tâche fallback pour item {item_id}: {error_reason}")

        # Créer une tâche minimale mais fonctionnelle
        fallback_task = TaskRequest(
            task_id=item_id,
            title=f"[ITEM INACCESSIBLE] {title}",
            description=f"""⚠️ **Item Monday.com inaccessible**

**Raison**: {error_reason}

**Action**: Cette tâche a été créée automatiquement car l'item Monday.com original n'était plus accessible lors du traitement du webhook.

**Informations disponibles du webhook**:
- ID Item: {item_id}
- Titre: {title}
- Type: {task_info.get('task_type', 'N/A')}
- Priorité: {task_info.get('priority', 'N/A')}

**Recommandation**: Vérifiez l'état de l'item dans Monday.com et relancez manuellement si nécessaire.""",
            branch_name=self._generate_branch_name(f"fallback-{item_id}"),
            repository_url=getattr(self.settings, "default_repo_url", "") or "",
            priority=task_info.get("priority", "low"),  # Priorité basse pour les fallbacks
            assignee=None,
            created_at=datetime.now(),
            task_type="analysis"  # Utiliser un type valide pour les fallbacks
        )

        return fallback_task

    async def handle_task_completion(self, task_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Gère la completion d'une tâche."""

        try:
            success = result.get("success", False)
            pr_url = result.get("pr_url")

            if success and pr_url:
                update_result = await self.monday_tool._arun(
                    action="complete_task",
                    item_id=task_id,
                    pr_url=pr_url
                )
            else:
                status = "Bloqué" if not success else "À vérifier"

                error_summary = ""
                if result.get("error_summary"):
                    error_summary = " | ".join(result["error_summary"][:3])

                comment = f"""❌ **Implémentation automatique échouée**

Erreurs rencontrées: {error_summary}

Intervention manuelle requise."""

                status_result = await self.monday_tool._arun(
                    action="update_item_status",
                    item_id=task_id,
                    status=status
                )

                comment_result = await self.monday_tool._arun(
                    action="add_comment",
                    item_id=task_id,
                    comment=comment
                )

                update_result = {
                    "success": status_result.get("success", False) and comment_result.get("success", False)
                }

            return update_result

        except Exception as e:
            logger.error(f"Erreur lors de la gestion de completion: {e}")
            return {"success": False, "error": str(e)}

    async def cleanup_stuck_tasks(self):
        """Nettoie les tâches restées en processing trop longtemps."""
        try:
            conn = await get_db_connection()

            result = await conn.execute("""
                UPDATE tasks
                SET internal_status = 'failed',
                    updated_at = NOW()
                WHERE internal_status = 'processing'
                AND updated_at < NOW() - INTERVAL '1 hour'
            """)

            logger.info(f"🧹 Tâches bloquées nettoyées: {result}")

        except Exception as e:
            logger.error(f"❌ Erreur lors du cleanup des tâches: {e}")
        finally:
            if 'conn' in locals():
                await conn.close()

    async def _check_duplicate_webhook(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Vérifie si un webhook similaire a déjà été traité récemment."""
        try:
            # Extraire l'identifiant de la tâche du payload
            if 'event' not in payload:
                return None

            event = payload['event']
            pulse_id = event.get('pulseId')
            pulse_name = event.get('pulseName', '')
            event_type = event.get('type')

            if not pulse_id or not pulse_name:
                return None

            conn = await get_db_connection()

            # Chercher des webhooks similaires traités dans les 2 dernières minutes
            # On recherche par titre ET type d'événement (pour permettre des vraies mises à jour)
            similar_webhook = await conn.fetchrow("""
                SELECT
                    webhook_events_id,
                    processed_at,
                    processing_status
                FROM webhook_events
                WHERE processing_status = 'processed'
                AND received_at >= NOW() - INTERVAL '2 minutes'
                AND payload::jsonb -> 'event' ->> 'pulseName' = $1
                AND payload::jsonb -> 'event' ->> 'type' = $2
                ORDER BY received_at DESC
                LIMIT 1
            """, pulse_name, event_type)

            await conn.close()

            return similar_webhook

        except Exception as e:
            logger.error(f"❌ Erreur vérification doublon webhook: {e}")
            return None
