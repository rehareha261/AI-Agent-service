"""
Service de persistence en temps réel pour le workflow.
Sauvegarde automatiquement toutes les données dans les tables de base2.sql.
"""

import asyncpg
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from decimal import Decimal

from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


class DatabasePersistenceService:
    """Service de persistence en temps réel pour le workflow."""

    def __init__(self):
        self.settings = get_settings()
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """Initialise la connexion à la base de données."""
        try:
            self.pool = await asyncpg.create_pool(
                self.settings.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("✅ Service de persistence initialisé")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation persistence: {e}")
            raise

    async def close(self):
        """Ferme les connexions à la base de données."""
        if self.pool:
            await self.pool.close()
            logger.info("🔒 Connexions fermées")

    async def create_task_from_monday(self, monday_payload: Dict[str, Any]) -> int:
        """Crée une nouvelle tâche depuis un webhook Monday.com."""
        async with self.pool.acquire() as conn:
            # Extraire les données du payload Monday
            item_id = monday_payload.get("pulseId") or monday_payload.get("itemId")
            board_id = monday_payload.get("boardId")
            item_name = monday_payload.get("pulseName") or monday_payload.get("itemName", "Tâche sans titre")

            # ✅ CORRECTION: Gérer les deux formats de colonnes Monday.com
            raw_columns = monday_payload.get("columnValues", monday_payload.get("column_values", {}))

            # Normaliser les colonnes en dictionnaire
            normalized_columns = {}
            if isinstance(raw_columns, list):
                # Format API Monday.com (liste)
                for col in raw_columns:
                    if isinstance(col, dict) and "id" in col:
                        normalized_columns[col["id"]] = col
                logger.info(f"🔧 Conversion colonnes liste → dict: {len(normalized_columns)} colonnes")
            elif isinstance(raw_columns, dict):
                # Format webhook (dictionnaire)
                normalized_columns = raw_columns
            else:
                logger.warning(f"⚠️ Format colonnes non reconnu: {type(raw_columns)}")
                normalized_columns = {}

            # Initialiser les variables
            description = ""
            priority = "medium"
            repository_url = ""

            # ✅ AMÉLIORATION: Fonction helper pour extraction sécurisée
            def safe_extract_text(col_id: str, default: str = "") -> str:
                """Extrait le texte d'une colonne de manière sécurisée."""
                col_data = normalized_columns.get(col_id, {})
                if isinstance(col_data, dict):
                    # Essayer plusieurs propriétés possibles
                    return (col_data.get("text") or
                           col_data.get("value") or
                           str(col_data.get("display_value", "")) or
                           default).strip()
                return default

            # ✅ AMÉLIORATION: Parser les colonnes avec noms multiples possibles
            for col_id, col_value in normalized_columns.items():
                col_id_lower = col_id.lower()

                # Description - essayer plusieurs variantes
                if any(keyword in col_id_lower for keyword in
                      ["description", "desc", "details", "text", "note", "comment", "sujet"]):
                    extracted_desc = safe_extract_text(col_id)
                    if extracted_desc and len(extracted_desc) > len(description):
                        description = extracted_desc
                        logger.info(f"📝 Description trouvée dans colonne '{col_id}': {description[:50]}...")

                # Priorité
                elif any(keyword in col_id_lower for keyword in ["priority", "priorité", "prio"]):
                    extracted_priority = safe_extract_text(col_id, "medium").lower()
                    if extracted_priority in ["low", "medium", "high", "urgent", "bas", "moyen", "élevé"]:
                        priority = extracted_priority
                        logger.info(f"📊 Priorité trouvée: {priority}")

                # URL Repository - essayer plusieurs variantes
                elif any(keyword in col_id_lower for keyword in
                        ["repo", "repository", "url", "github", "git", "project"]):
                    extracted_url = safe_extract_text(col_id)
                    if extracted_url and ("github.com" in extracted_url or "git" in extracted_url):
                        repository_url = extracted_url
                        logger.info(f"🔗 URL repository trouvée dans colonne '{col_id}': {repository_url}")

            # ✅ FALLBACK: Si pas d'URL trouvée, essayer d'extraire depuis la description
            if not repository_url and description:
                from utils.github_parser import extract_github_url_from_description
                extracted_url = extract_github_url_from_description(description)
                if extracted_url:
                    repository_url = extracted_url
                    logger.info(f"🎯 URL GitHub extraite de la description: {repository_url}")

            # ✅ VALIDATION: Vérifier que nous avons au minimum un titre et une URL
            if not repository_url:
                logger.warning(f"⚠️ Aucune URL repository trouvée pour l'item {item_id}")
                logger.warning(f"📋 Colonnes disponibles: {list(normalized_columns.keys())}")
                logger.warning(f"📝 Description: {description[:100]}...")

            # Insérer la tâche
            task_id = await conn.fetchval("""
                INSERT INTO tasks (
                    monday_item_id, monday_board_id, title, description,
                    priority, repository_url, repository_name,
                    monday_status, internal_status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING tasks_id
            """,
                item_id, board_id, item_name, description,
                priority, repository_url,
                repository_url.split('/')[-1] if repository_url else "",
                "nouveau", "pending"
            )

            logger.info(f"📝 Tâche créée: {task_id} - {item_name}")
            logger.info(f"🔗 URL: {repository_url or 'NON DÉFINIE'}")
            logger.info(f"📄 Description: {description[:50] + '...' if description else 'NON DÉFINIE'}")
            return task_id

    async def start_task_run(self, task_id: Optional[int], celery_task_id: str,
                            ai_provider: str = "claude", custom_run_id: str = None) -> int:
        """Démarre une nouvelle exécution de tâche."""
        async with self.pool.acquire() as conn:
            # Utiliser custom_run_id si fourni, sinon celery_task_id
            effective_task_id = custom_run_id or celery_task_id

            # Obtenir le numéro de run suivant
            if task_id:
                run_number = await conn.fetchval("""
                    SELECT COALESCE(MAX(run_number), 0) + 1
                    FROM task_runs WHERE task_id = $1
                """, task_id)
            else:
                # Pour les tâches sans ID, utiliser un compteur global
                run_number = await conn.fetchval("""
                    SELECT COALESCE(MAX(run_number), 0) + 1
                    FROM task_runs WHERE task_id IS NULL
                """) or 1

            # Créer le run - task_id peut être NULL
            run_id = await conn.fetchval("""
                INSERT INTO task_runs (
                    task_id, run_number, status, celery_task_id,
                    ai_provider, current_node, progress_percentage
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING tasks_runs_id
            """,
                task_id, run_number, "started", effective_task_id,
                ai_provider, "prepare_environment", 0
            )

            # Mettre à jour la tâche si task_id existe
            if task_id:
                await conn.execute("""
                    UPDATE tasks
                    SET last_run_id = $1, internal_status = $2, started_at = NOW()
                    WHERE tasks_id = $3
                """, run_id, "processing", task_id)

            logger.info(f"🚀 Run démarré: {run_id} (UUID: {effective_task_id}) pour tâche {task_id or 'standalone'}")
            return run_id

    def _truncate_node_name(self, node_name: str, max_length: int = 50) -> str:
        """
        Tronque le nom du nœud s'il est trop long pour la base de données.
        Garde les parties importantes et indique la troncature.

        Note: max_length réduit à 50 pour assurer compatibilité avec colonnes VARCHAR(100)
        """
        if len(node_name) <= max_length:
            return node_name

        # Cas spéciaux pour les noms de canal - très court pour éviter value too long
        if node_name.startswith("ChannelWrite<"):
            return "ChannelWrite<...>"

        if node_name.startswith("__start__") or node_name.startswith("__end__"):
            # Préserver les noms de démarrage/fin importants
            return node_name[:max_length-3] + "..."

        # Pour les autres noms longs, tronquer intelligemment
        if ":" in node_name:
            # Si contient des deux-points, garder la partie avant
            prefix = node_name.split(":")[0]
            if len(prefix) <= max_length - 4:
                return prefix + ":..."

        # Tronquer et ajouter des points de suspension
        return node_name[:max_length-3] + "..."

    async def create_run_step(self, task_run_id: int, node_name: str,
                             step_order: int, input_data: Dict[str, Any] = None) -> int:
        """Crée une nouvelle étape de run."""
        async with self.pool.acquire() as conn:
            # ✅ CORRECTION: Tronquer le nom du nœud s'il est trop long
            truncated_node_name = self._truncate_node_name(node_name)

            # ✅ SÉRIALISATION JSON ROBUSTE: Gestion complète avec fallbacks sécurisés
            input_data_json = None
            if input_data is not None:
                try:
                    # Étape 1: Nettoyer les données pour la sérialisation JSON
                    clean_data = self._clean_for_json_serialization(input_data)

                    # Étape 2: Tenter la sérialisation directe
                    input_data_json = json.dumps(clean_data, ensure_ascii=False, separators=(',', ':'))

                    # Étape 3: Vérification de la taille pour éviter les surcharges DB
                    max_size = 64000  # Limite PostgreSQL pour JSONB
                    if len(input_data_json) > max_size:
                        logger.warning(f"⚠️ Données JSON trop volumineuses ({len(input_data_json)} chars), troncature nécessaire")
                        # Créer une version tronquée intelligemment
                        truncated_data = {
                            "truncated": True,
                            "original_size": len(input_data_json),
                            "node_name": clean_data.get("node_name") if isinstance(clean_data, dict) else None,
                            "summary": str(clean_data)[:1000] + "..." if len(str(clean_data)) > 1000 else str(clean_data),
                            "truncated_at": datetime.now().isoformat()
                        }
                        input_data_json = json.dumps(truncated_data, ensure_ascii=False, separators=(',', ':'))

                except (TypeError, ValueError, OverflowError) as e:
                    logger.warning(f"⚠️ Échec sérialisation input_data: {e}. Utilisation fallback sécurisé.")
                    # Fallback robuste avec informations de debug utiles
                    fallback_data = {
                        "serialization_error": True,
                        "error_type": type(e).__name__,
                        "error_message": str(e)[:200],
                        "original_type": str(type(input_data)),
                        "data_structure": self._get_data_structure_info(input_data),
                        "timestamp": datetime.now().isoformat()
                    }

                    # Essayer d'extraire au moins quelques informations utiles
                    try:
                        if hasattr(input_data, '__dict__'):
                            fallback_data["available_attributes"] = list(input_data.__dict__.keys())[:10]
                        elif isinstance(input_data, dict):
                            fallback_data["dict_keys"] = list(input_data.keys())[:10]
                        elif isinstance(input_data, (list, tuple)):
                            fallback_data["sequence_length"] = len(input_data)
                            fallback_data["first_elements"] = [str(item)[:50] for item in input_data[:3]]
                    except Exception:
                        pass  # Ignore si même l'extraction d'infos échoue

                    input_data_json = json.dumps(fallback_data, ensure_ascii=False, separators=(',', ':'))

            step_id = await conn.fetchval("""
                INSERT INTO run_steps (
                    task_run_id, node_name, step_order, status,
                    input_data, started_at
                ) VALUES ($1, $2, $3, $4, $5, NOW())
                RETURNING run_steps_id
            """,
                task_run_id, truncated_node_name, step_order, "running",
                input_data_json
            )

            # Mettre à jour le run avec le nœud actuel (avec troncature pour éviter value too long)
            await conn.execute("""
                UPDATE task_runs
                SET current_node = $1, progress_percentage = $2
                WHERE tasks_runs_id = $3
            """, truncated_node_name, min(step_order * 12, 90), task_run_id)

            logger.debug(f"📍 Étape créée: {node_name} ({step_id})")
            return step_id

    def _clean_for_json_serialization(self, data: Any) -> Any:
        """
        Nettoie récursivement les données pour la sérialisation JSON.
        Convertit les objets Pydantic, dataclasses, et autres objets complexes.
        """
        if data is None:
            return None
        elif isinstance(data, (str, int, float, bool)):
            return data
        elif isinstance(data, (list, tuple)):
            return [self._clean_for_json_serialization(item) for item in data]
        elif isinstance(data, dict):
            return {
                str(key): self._clean_for_json_serialization(value)
                for key, value in data.items()
            }
        elif hasattr(data, 'dict') and callable(getattr(data, 'dict')):
            # Pydantic BaseModel
            return self._clean_for_json_serialization(data.dict())
        elif hasattr(data, '__dict__'):
            # Objet avec attributs __dict__
            return self._clean_for_json_serialization(data.__dict__)
        elif hasattr(data, '_asdict') and callable(getattr(data, '_asdict')):
            # namedtuple
            return self._clean_for_json_serialization(data._asdict())
        else:
            # Fallback: convertir en string
            return str(data)

    def _get_data_structure_info(self, data: Any) -> str:
        """
        Obtient une description sécurisée de la structure de données pour le debug.

        Args:
            data: Données à analyser

        Returns:
            Description textuelle de la structure
        """
        try:
            if data is None:
                return "None"
            elif isinstance(data, (str, int, float, bool)):
                return f"{type(data).__name__}({len(str(data))} chars)" if isinstance(data, str) else f"{type(data).__name__}"
            elif isinstance(data, (list, tuple)):
                return f"{type(data).__name__}(length={len(data)}, types={[type(item).__name__ for item in data[:3]]})"
            elif isinstance(data, dict):
                return f"dict(keys={len(data)}, sample_keys={list(data.keys())[:5]})"
            elif hasattr(data, '__dict__'):
                attrs = list(data.__dict__.keys())[:5]
                return f"{type(data).__name__}(attributes={attrs})"
            else:
                return f"{type(data).__name__}(repr_length={len(repr(data)[:100])})"
        except Exception:
            return f"{type(data).__name__}(analysis_failed)"

    async def complete_run_step(self, step_id: int, status: str = "completed",
                               output_data: Dict[str, Any] = None,
                               error_details: str = None):
        """Termine une étape de run."""
        async with self.pool.acquire() as conn:
            # Calculer la durée
            step_info = await conn.fetchrow("""
                SELECT started_at, task_run_id FROM run_steps WHERE run_steps_id = $1
            """, step_id)

            if step_info:
                duration = (datetime.now(timezone.utc) - step_info['started_at']).total_seconds()

                # ✅ CORRECTION: Sérialisation JSON robuste pour output_data
                output_data_json = None
                if output_data:
                    try:
                        clean_output = self._clean_for_json_serialization(output_data)
                        output_data_json = json.dumps(clean_output)
                    except (TypeError, ValueError) as e:
                        logger.warning(f"⚠️ Impossible de sérialiser output_data: {e}")
                        output_data_json = json.dumps({
                            "error": "Sérialisation échouée",
                            "original_type": str(type(output_data)),
                            "str_representation": str(output_data)[:500]
                        })

                await conn.execute("""
                    UPDATE run_steps
                    SET status = $1, completed_at = NOW(), duration_seconds = $2,
                        output_data = $3, error_details = $4
                    WHERE run_steps_id = $5
                """,
                    status, int(duration),
                    output_data_json,
                    error_details, step_id
                )

                logger.debug(f"✅ Étape terminée: {step_id} - {status}")

    async def log_ai_interaction(self, run_step_id: int, ai_provider: str,
                                model: str, prompt: str, response: str = None,
                                token_usage: Dict[str, int] = None,
                                latency_ms: int = None):
        """Enregistre une interaction IA."""
        async with self.pool.acquire() as conn:
            interaction_id = await conn.fetchval("""
                INSERT INTO ai_interactions (
                    run_step_id, ai_provider, model_name, prompt,
                    response, token_usage, latency_ms
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING ai_interactions_id
            """,
                run_step_id, ai_provider, model, prompt,
                response, json.dumps(token_usage) if token_usage else None,
                latency_ms
            )

            logger.debug(f"🤖 Interaction IA loggée: {interaction_id}")
            return interaction_id

    async def log_code_generation(self, task_run_id: int, provider: str, model: str,
                                 generation_type: str, prompt: str,
                                 generated_code: str = None, tokens_used: int = None,
                                 response_time_ms: int = None, cost_estimate: float = None,
                                 files_modified: List[str] = None):
        """Enregistre une génération de code."""
        async with self.pool.acquire() as conn:
            gen_id = await conn.fetchval("""
                INSERT INTO ai_code_generations (
                    task_run_id, provider, model, generation_type, prompt,
                    generated_code, tokens_used, response_time_ms, cost_estimate,
                    files_modified
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING ai_code_generations_id
            """,
                task_run_id, provider, model, generation_type, prompt,
                generated_code, tokens_used, response_time_ms,
                Decimal(str(cost_estimate)) if cost_estimate else None,
                json.dumps(files_modified) if files_modified else None
            )

            logger.debug(f"💾 Génération code loggée: {gen_id}")
            return gen_id

    async def log_test_results(self, task_run_id: int, passed: bool, status: str,
                              tests_total: int = 0, tests_passed: int = 0,
                              tests_failed: int = 0, tests_skipped: int = 0,
                              coverage_percentage: float = None,
                              pytest_report: Dict[str, Any] = None,
                              duration_seconds: int = None):
        """Enregistre les résultats de tests."""
        async with self.pool.acquire() as conn:
            test_id = await conn.fetchval("""
                INSERT INTO test_results (
                    task_run_id, passed, status, tests_total, tests_passed,
                    tests_failed, tests_skipped, coverage_percentage,
                    pytest_report, duration_seconds
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING test_results_id
            """,
                task_run_id, passed, status, tests_total, tests_passed,
                tests_failed, tests_skipped,
                Decimal(str(coverage_percentage)) if coverage_percentage else None,
                json.dumps(pytest_report) if pytest_report else None,
                duration_seconds
            )

            logger.debug(f"🧪 Résultats tests loggés: {test_id}")
            return test_id

    async def create_pull_request(self, task_id: int, task_run_id: int,
                                 github_pr_number: int, github_pr_url: str,
                                 pr_title: str, pr_description: str = None,
                                 head_sha: str = None, base_branch: str = "main",
                                 feature_branch: str = None):
        """Enregistre une pull request."""
        async with self.pool.acquire() as conn:
            pr_id = await conn.fetchval("""
                INSERT INTO pull_requests (
                    task_id, task_run_id, github_pr_number, github_pr_url,
                    pr_title, pr_description, pr_status, head_sha,
                    base_branch, feature_branch
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING pull_requests_id
            """,
                task_id, task_run_id, github_pr_number, github_pr_url,
                pr_title, pr_description, "open", head_sha,
                base_branch, feature_branch
            )

            # Mettre à jour le run avec l'URL de la PR
            await conn.execute("""
                UPDATE task_runs
                SET pull_request_url = $1
                WHERE tasks_runs_id = $2
            """, github_pr_url, task_run_id)

            logger.info(f"🔀 Pull request créée: {pr_id} - {github_pr_url}")
            return pr_id

    async def complete_task_run(self, task_run_id: int, status: str = "completed",
                               result: Dict[str, Any] = None, error_message: str = None):
        """Termine une exécution de tâche."""
        async with self.pool.acquire() as conn:
            # Calculer la durée totale
            run_info = await conn.fetchrow("""
                SELECT started_at, task_id FROM task_runs WHERE tasks_runs_id = $1
            """, task_run_id)

            if run_info:
                duration = (datetime.now(timezone.utc) - run_info['started_at']).total_seconds()

                # Mettre à jour le run
                await conn.execute("""
                    UPDATE task_runs
                    SET status = $1, completed_at = NOW(), duration_seconds = $2,
                        result = $3, error_message = $4, progress_percentage = $5
                    WHERE tasks_runs_id = $6
                """,
                    status, int(duration),
                    json.dumps(result) if result else None,
                    error_message, 100 if status == "completed" else 50,
                    task_run_id
                )

                # Mettre à jour le statut de la tâche
                final_status = "completed" if status == "completed" else "failed"
                await conn.execute("""
                    UPDATE tasks
                    SET internal_status = $1, completed_at = NOW()
                    WHERE tasks_id = $2
                """, final_status, run_info['task_id'])

                logger.info(f"🏁 Run terminé: {task_run_id} - {status}")

    async def log_application_event(self, task_id: int = None, task_run_id: int = None,
                                   run_step_id: int = None, level: str = "INFO",
                                   source_component: str = "workflow",
                                   action: str = "", message: str = "",
                                   metadata: Dict[str, Any] = None):
        """Enregistre un événement d'application."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO application_logs (
                    task_id, task_run_id, run_step_id, level,
                    source_component, action, message, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                task_id, task_run_id, run_step_id, level,
                source_component, action, message,
                json.dumps(self._clean_for_json_serialization(metadata)) if metadata else None
            )

    async def record_performance_metrics(self, task_id: int, task_run_id: int,
                                       total_duration_seconds: int = None,
                                       ai_processing_time_seconds: int = None,
                                       testing_time_seconds: int = None,
                                       total_ai_calls: int = 0,
                                       total_tokens_used: int = 0,
                                       total_ai_cost: float = 0.0,
                                       test_coverage_final: float = None,
                                       retry_attempts: int = 0):
        """Enregistre les métriques de performance."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO performance_metrics (
                    task_id, task_run_id, total_duration_seconds,
                    ai_processing_time_seconds, testing_time_seconds,
                    total_ai_calls, total_tokens_used, total_ai_cost,
                    test_coverage_final, retry_attempts
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
                task_id, task_run_id, total_duration_seconds,
                ai_processing_time_seconds, testing_time_seconds,
                total_ai_calls, total_tokens_used, Decimal(str(total_ai_cost)),
                Decimal(str(test_coverage_final)) if test_coverage_final else None,
                retry_attempts
            )

            logger.info(f"📊 Métriques enregistrées pour run {task_run_id}")

    # ===== MÉTHODES WEBHOOK =====

    async def _log_webhook_event(self, source: str, event_type: str, payload: Dict[str, Any],
                                headers: Dict[str, str] = None, signature: str = None) -> int:
        """Enregistre un événement webhook."""
        async with self.pool.acquire() as conn:
            webhook_id = await conn.fetchval("""
                INSERT INTO webhook_events (
                    source, event_type, payload, headers, signature, received_at
                ) VALUES ($1, $2, $3, $4, $5, NOW())
                RETURNING webhook_events_id
            """,
                source, event_type, json.dumps(payload),
                json.dumps(headers) if headers else None, signature
            )

            return webhook_id

    async def _mark_webhook_processed(self, webhook_id: int, success: bool, error_message: str = None):
        """Marque un webhook comme traité."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE webhook_events
                SET processed = $1, processing_status = $2, processed_at = NOW(),
                    error_message = $3
                WHERE webhook_events_id = $4
            """,
                success, "completed" if success else "failed",
                error_message, webhook_id
            )

    async def _link_webhook_to_task(self, webhook_id: int, task_id: int):
        """Lie un webhook à une tâche."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE webhook_events
                SET related_task_id = $1
                WHERE webhook_events_id = $2
            """, task_id, webhook_id)

    async def _find_task_by_monday_id(self, monday_item_id: int) -> Optional[int]:
        """Recherche une tâche par son ID Monday.com."""
        async with self.pool.acquire() as conn:
            task_id = await conn.fetchval("""
                SELECT tasks_id FROM tasks WHERE monday_item_id = $1
            """, monday_item_id)

            return task_id

    async def _update_task_from_monday(self, task_id: int, monday_payload: Dict[str, Any]) -> int:
        """Met à jour une tâche existante depuis un payload Monday.com."""
        async with self.pool.acquire() as conn:
            # Extraire les nouvelles données avec protection des types
            item_name = monday_payload.get("pulseName") or monday_payload.get("itemName", "")

            # ✅ PROTECTION: S'assurer que value est un dictionnaire
            value_data = monday_payload.get("value", {})
            if isinstance(value_data, dict):
                label_data = value_data.get("label", {})
                if isinstance(label_data, dict):
                    status = label_data.get("text", "")
                else:
                    status = ""
            else:
                status = ""

            if item_name:
                await conn.execute("""
                    UPDATE tasks
                    SET title = $1, monday_status = $2, updated_at = NOW()
                    WHERE tasks_id = $3
                """, item_name, status, task_id)

            return task_id

    async def save_run_step_checkpoint(self, step_id: int, checkpoint_data: Dict[str, Any]):
        """Sauvegarde un checkpoint pour une étape de run."""
        try:
            async with self.pool.acquire() as conn:
                # Nettoyer les données pour la sérialisation JSON
                clean_data = self._clean_for_json_serialization(checkpoint_data)
                checkpoint_json = json.dumps(clean_data)

                await conn.execute("""
                    UPDATE run_steps
                    SET checkpoint_data = $1, checkpoint_saved_at = NOW()
                    WHERE run_steps_id = $2
                """, checkpoint_json, step_id)

                logger.debug(f"💾 Checkpoint sauvegardé pour étape {step_id}")

        except Exception as e:
            logger.warning(f"⚠️ Erreur sauvegarde checkpoint étape {step_id}: {e}")
            # Ne pas faire échouer le workflow pour un problème de checkpoint

    async def get_step_id_by_task_run_and_node(self, task_run_id: int, node_name: str) -> Optional[int]:
        """Récupère l'ID du step à partir du task_run_id et du nom du nœud."""
        try:
            async with self.pool.acquire() as conn:
                # Tronquer le nom du nœud pour correspondre à ce qui est en base
                truncated_node_name = self._truncate_node_name(node_name)

                step_id = await conn.fetchval("""
                    SELECT run_steps_id FROM run_steps
                    WHERE task_run_id = $1 AND node_name = $2
                    ORDER BY step_order DESC
                    LIMIT 1
                """, task_run_id, truncated_node_name)

                return step_id

        except Exception as e:
            logger.warning(f"⚠️ Erreur récupération step_id pour task_run_id={task_run_id}, node={node_name}: {e}")
            return None

    async def save_node_checkpoint(self, task_run_id: int, node_name: str, checkpoint_data: Dict[str, Any]):
        """
        Sauvegarde un checkpoint pour un nœud avec gestion robuste des steps.

        Cette méthode garantit l'existence d'un step avant de sauvegarder le checkpoint,
        avec gestion des race conditions et validation des données.

        Args:
            task_run_id: ID du run de tâche
            node_name: Nom du nœud (sera tronqué si nécessaire)
            checkpoint_data: Données du checkpoint à sauvegarder

        Raises:
            ValueError: Si les paramètres sont invalides
        """
        # ✅ VALIDATION: Vérifier les paramètres d'entrée
        if not task_run_id or task_run_id <= 0:
            raise ValueError(f"task_run_id invalide: {task_run_id}")
        if not node_name or not isinstance(node_name, str):
            raise ValueError(f"node_name invalide: {node_name}")
        if not isinstance(checkpoint_data, dict):
            raise ValueError(f"checkpoint_data doit être un dictionnaire: {type(checkpoint_data)}")

        try:
            # ✅ ROBUSTESSE: Utiliser une transaction pour éviter les race conditions
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Récupérer ou créer le step de manière atomique
                    step_id = await self._get_or_create_step_atomic(
                        conn, task_run_id, node_name, checkpoint_data
                    )

                    if step_id:
                        # Nettoyer les données avant sauvegarde
                        cleaned_data = self._clean_for_json_serialization(checkpoint_data)

                        # Sauvegarder le checkpoint
                        await self._save_checkpoint_atomic(conn, step_id, cleaned_data)

                        logger.debug(f"💾 Checkpoint sauvé pour {node_name} (step_id: {step_id}, task_run_id: {task_run_id})")
                    else:
                        logger.error(f"❌ Impossible de créer ou récupérer step_id pour task_run_id={task_run_id}, node={node_name}")

        except ValueError as ve:
            logger.error(f"❌ Erreur validation checkpoint {node_name}: {ve}")
            raise  # Re-lever les erreurs de validation
        except Exception as e:
            logger.warning(f"⚠️ Erreur sauvegarde checkpoint {node_name}: {e}")
                         # Ne pas faire échouer le workflow pour un problème de checkpoint non-critique

    async def _get_or_create_step_atomic(self, conn, task_run_id: int, node_name: str, checkpoint_data: Dict[str, Any]) -> Optional[int]:
        """
        Récupère ou crée un step de manière atomique pour éviter les race conditions.

        Args:
            conn: Connexion de base de données (dans une transaction)
            task_run_id: ID du run de tâche
            node_name: Nom du nœud
            checkpoint_data: Données pour créer le step si nécessaire

        Returns:
            ID du step ou None si impossible
        """
        try:
            # Tronquer le nom du nœud pour correspondre à la base
            truncated_node_name = self._truncate_node_name(node_name)

            # Essayer de récupérer un step existant
            step_id = await conn.fetchval("""
                SELECT run_steps_id FROM run_steps
                WHERE task_run_id = $1 AND node_name = $2
                ORDER BY step_order DESC
                LIMIT 1
            """, task_run_id, truncated_node_name)

            if step_id:
                logger.debug(f"📋 Step existant trouvé: {step_id} pour {node_name}")
                return step_id

            # Si aucun step trouvé, en créer un nouveau
            logger.info(f"🔄 Création nouveau step pour {node_name} (task_run_id: {task_run_id})")

            # Déterminer le step_order suivant
            next_order = await conn.fetchval("""
                SELECT COALESCE(MAX(step_order), 0) + 1
                FROM run_steps WHERE task_run_id = $1
            """, task_run_id) or 1

            # Déterminer le statut approprié
            status = checkpoint_data.get("status", "completed")
            if status not in ["pending", "running", "completed", "failed", "skipped"]:
                status = "completed"

            # Créer le step avec sérialisation JSON correcte
            clean_checkpoint = self._clean_for_json_serialization(checkpoint_data)
            checkpoint_json = json.dumps(clean_checkpoint, ensure_ascii=False, separators=(',', ':'))

            step_id = await conn.fetchval("""
                INSERT INTO run_steps (task_run_id, node_name, status, step_order, started_at, input_data)
                VALUES ($1, $2, $3, $4, NOW(), $5)
                RETURNING run_steps_id
            """, task_run_id, truncated_node_name, status, next_order,
                checkpoint_json)

            logger.info(f"✅ Step créé: {step_id} pour {node_name} (order: {next_order})")
            return step_id

        except Exception as e:
            logger.error(f"❌ Erreur création step atomique pour {node_name}: {e}")
            return None

    async def _save_checkpoint_atomic(self, conn, step_id: int, checkpoint_data: Dict[str, Any]):
        """
        Sauvegarde un checkpoint de manière atomique.

        Args:
            conn: Connexion de base de données (dans une transaction)
            step_id: ID du step
            checkpoint_data: Données du checkpoint (déjà nettoyées)
        """
        try:
            # Sérialiser les données en JSON
            checkpoint_json = json.dumps(checkpoint_data, ensure_ascii=False, separators=(',', ':'))

            # Vérifier si un checkpoint existe déjà
            existing_checkpoint = await conn.fetchval("""
                SELECT checkpoint_id FROM run_step_checkpoints
                WHERE step_id = $1
                ORDER BY created_at DESC
                LIMIT 1
            """, step_id)

            if existing_checkpoint:
                # Mettre à jour le checkpoint existant
                await conn.execute("""
                    UPDATE run_step_checkpoints
                    SET checkpoint_data = $2, updated_at = NOW()
                    WHERE checkpoint_id = $1
                """, existing_checkpoint, checkpoint_json)
                logger.debug(f"📝 Checkpoint mis à jour: {existing_checkpoint}")
            else:
                # Créer un nouveau checkpoint
                checkpoint_id = await conn.fetchval("""
                    INSERT INTO run_step_checkpoints (step_id, checkpoint_data, created_at)
                    VALUES ($1, $2, NOW())
                    RETURNING checkpoint_id
                """, step_id, checkpoint_json)
                logger.debug(f"📝 Nouveau checkpoint créé: {checkpoint_id}")

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde checkpoint atomique: {e}")
            raise


# Instance globale
db_persistence = DatabasePersistenceService()