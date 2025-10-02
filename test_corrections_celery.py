#!/usr/bin/env python3
"""Script de test pour vérifier les corrections des problèmes Celery."""

import asyncio
import json
import time
import hashlib
from typing import Dict, Any
from services.webhook_service import WebhookService
from services.monitoring_service import monitoring_service
from models.schemas import TaskRequest
from utils.logger import get_logger

logger = get_logger(__name__)

class CeleryFixesTest:
    """Tests pour vérifier les corrections des problèmes Celery."""
    
    def __init__(self):
        self.webhook_service = WebhookService()
        self.test_results = []
        
    async def test_duplicate_webhook_prevention(self):
        """Test de prévention des webhooks dupliqués."""
        logger.info("🧪 Test 1: Prévention des webhooks dupliqués")
        
        # Créer un webhook de test
        test_payload = {
            "event": {
                "pulseId": "test_duplicate_123",
                "boardId": "987654321",
                "pulseName": "Test duplication",
                "columnValues": {}
            },
            "type": "create_pulse"
        }
        
        try:
            # Premier appel
            start_time = time.time()
            result1 = await self.webhook_service.process_webhook(test_payload)
            end_time = time.time()
            
            logger.info(f"Premier webhook traité en {end_time - start_time:.2f}s")
            logger.info(f"Résultat 1: {result1}")
            
            # Deuxième appel immédiat (devrait être bloqué)
            start_time = time.time()
            result2 = await self.webhook_service.process_webhook(test_payload)
            end_time = time.time()
            
            logger.info(f"Deuxième webhook traité en {end_time - start_time:.2f}s")
            logger.info(f"Résultat 2: {result2}")
            
            # Vérifier que le deuxième a été dédupliqué
            is_deduplicated = result2.get('deduplicated', False) or result2.get('task_exists', False)
            
            if is_deduplicated:
                logger.info("✅ Test déduplication réussi - webhook dupliqué bloqué")
                self.test_results.append({
                    "test": "duplicate_prevention",
                    "status": "passed",
                    "message": "Webhook dupliqué correctement bloqué"
                })
            else:
                logger.warning("⚠️ Test déduplication échoué - webhook dupliqué traité")
                self.test_results.append({
                    "test": "duplicate_prevention", 
                    "status": "failed",
                    "message": "Webhook dupliqué non bloqué"
                })
                
        except Exception as e:
            logger.error(f"❌ Erreur test déduplication: {e}")
            self.test_results.append({
                "test": "duplicate_prevention",
                "status": "error", 
                "message": str(e)
            })
    
    async def test_monitoring_resilience(self):
        """Test de résilience du monitoring."""
        logger.info("🧪 Test 2: Résilience du monitoring")
        
        try:
            # Vérifier que le monitoring est actif
            initial_status = monitoring_service.is_monitoring_active
            logger.info(f"Statut initial du monitoring: {initial_status}")
            
            if not initial_status:
                # Démarrer le monitoring
                await monitoring_service.start_monitoring()
                await asyncio.sleep(2)  # Laisser le temps de démarrer
            
            # Vérifier les tâches en arrière-plan
            background_tasks_count = len(monitoring_service.background_tasks)
            logger.info(f"Nombre de tâches de monitoring: {background_tasks_count}")
            
            # Attendre quelques secondes pour voir si les tâches restent actives
            await asyncio.sleep(10)
            
            # Vérifier que les tâches sont toujours actives
            active_tasks = sum(1 for task in monitoring_service.background_tasks if not task.done())
            logger.info(f"Tâches actives après 10s: {active_tasks}/{background_tasks_count}")
            
            if active_tasks >= 3:  # Au moins 3 tâches principales + watchdog
                logger.info("✅ Test monitoring réussi - tâches restent actives")
                self.test_results.append({
                    "test": "monitoring_resilience",
                    "status": "passed",
                    "message": f"{active_tasks} tâches de monitoring actives"
                })
            else:
                logger.warning("⚠️ Test monitoring échoué - tâches terminées prématurément")
                self.test_results.append({
                    "test": "monitoring_resilience",
                    "status": "failed",
                    "message": f"Seulement {active_tasks} tâches actives"
                })
                
        except Exception as e:
            logger.error(f"❌ Erreur test monitoring: {e}")
            self.test_results.append({
                "test": "monitoring_resilience",
                "status": "error",
                "message": str(e)
            })
    
    async def test_webhook_signature_generation(self):
        """Test de génération de signature webhook."""
        logger.info("🧪 Test 3: Génération de signatures webhook")
        
        try:
            # Créer des webhooks identiques
            payload1 = {
                "event": {"pulseId": "123", "pulseName": "Test"},
                "type": "create_pulse"
            }
            payload2 = {
                "event": {"pulseId": "123", "pulseName": "Test"},
                "type": "create_pulse"
            }
            
            # Tester la génération de signature
            signature1 = self.webhook_service._create_webhook_signature(payload1)
            signature2 = self.webhook_service._create_webhook_signature(payload2)
            
            logger.info(f"Signature 1: {signature1[:16]}...")
            logger.info(f"Signature 2: {signature2[:16]}...")
            
            if signature1 == signature2:
                logger.info("✅ Test signatures réussi - signatures identiques pour payloads identiques")
                self.test_results.append({
                    "test": "signature_generation",
                    "status": "passed",
                    "message": "Signatures correctement générées"
                })
            else:
                logger.warning("⚠️ Test signatures échoué - signatures différentes")
                self.test_results.append({
                    "test": "signature_generation",
                    "status": "failed",
                    "message": "Signatures incohérentes"
                })
                
            # Test avec payloads différents
            payload3 = {
                "event": {"pulseId": "456", "pulseName": "Test Different"},
                "type": "create_pulse"
            }
            signature3 = self.webhook_service._create_webhook_signature(payload3)
            
            if signature1 != signature3:
                logger.info("✅ Signatures différentes pour payloads différents")
            else:
                logger.warning("⚠️ Signatures identiques pour payloads différents")
                
        except Exception as e:
            logger.error(f"❌ Erreur test signatures: {e}")
            self.test_results.append({
                "test": "signature_generation",
                "status": "error",
                "message": str(e)
            })
    
    async def test_webhook_cache_cleanup(self):
        """Test de nettoyage du cache webhook."""
        logger.info("🧪 Test 4: Nettoyage du cache webhook")
        
        try:
            # Ajouter des entrées dans le cache
            old_timestamp = time.time() - 400  # Plus de 5 minutes (300s)
            recent_timestamp = time.time() - 100  # Moins de 5 minutes
            
            self.webhook_service._webhook_cache = {
                "old_signature": {"timestamp": old_timestamp, "task_id": "old_task"},
                "recent_signature": {"timestamp": recent_timestamp, "task_id": "recent_task"}
            }
            
            logger.info(f"Cache initial: {len(self.webhook_service._webhook_cache)} entrées")
            
            # Déclencher le nettoyage
            self.webhook_service._cleanup_webhook_cache(time.time())
            
            remaining_count = len(self.webhook_service._webhook_cache)
            logger.info(f"Cache après nettoyage: {remaining_count} entrées")
            
            # Vérifier que seules les entrées récentes restent
            if remaining_count == 1 and "recent_signature" in self.webhook_service._webhook_cache:
                logger.info("✅ Test nettoyage cache réussi")
                self.test_results.append({
                    "test": "cache_cleanup",
                    "status": "passed",
                    "message": "Cache nettoyé correctement"
                })
            else:
                logger.warning("⚠️ Test nettoyage cache échoué")
                self.test_results.append({
                    "test": "cache_cleanup",
                    "status": "failed", 
                    "message": f"Cache non nettoyé correctement: {remaining_count} entrées restantes"
                })
                
        except Exception as e:
            logger.error(f"❌ Erreur test nettoyage cache: {e}")
            self.test_results.append({
                "test": "cache_cleanup",
                "status": "error",
                "message": str(e)
            })
    
    async def run_all_tests(self):
        """Exécute tous les tests."""
        logger.info("🚀 Démarrage des tests de correction Celery")
        
        # Tests séquentiels
        await self.test_webhook_signature_generation()
        await self.test_webhook_cache_cleanup()
        await self.test_duplicate_webhook_prevention()
        await self.test_monitoring_resilience()
        
        # Résumé des résultats
        logger.info("\n📊 RÉSUMÉ DES TESTS")
        logger.info("=" * 50)
        
        passed = sum(1 for result in self.test_results if result["status"] == "passed")
        failed = sum(1 for result in self.test_results if result["status"] == "failed")
        errors = sum(1 for result in self.test_results if result["status"] == "error")
        total = len(self.test_results)
        
        for result in self.test_results:
            status_emoji = {"passed": "✅", "failed": "❌", "error": "💥"}.get(result["status"], "❓")
            logger.info(f"{status_emoji} {result['test']}: {result['message']}")
        
        logger.info(f"\nTotal: {total} tests")
        logger.info(f"Réussites: {passed}")
        logger.info(f"Échecs: {failed}")
        logger.info(f"Erreurs: {errors}")
        
        success_rate = (passed / total * 100) if total > 0 else 0
        logger.info(f"Taux de réussite: {success_rate:.1f}%")
        
        if success_rate >= 75:
            logger.info("🎉 Tests majoritairement réussis - corrections efficaces")
        else:
            logger.warning("⚠️ Tests en échec - corrections nécessaires")
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "success_rate": success_rate,
            "details": self.test_results
        }

async def main():
    """Point d'entrée principal."""
    tester = CeleryFixesTest()
    results = await tester.run_all_tests()
    
    # Sauvegarder les résultats
    with open("test_corrections_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info("📁 Résultats sauvés dans test_corrections_results.json")
    return results

if __name__ == "__main__":
    asyncio.run(main()) 