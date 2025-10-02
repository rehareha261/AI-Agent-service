#!/usr/bin/env python3
"""Test rapide pour vérifier les corrections du workflow."""

import asyncio
from graph.workflow_graph import create_workflow_graph
from models.schemas import TaskRequest
from services.monitoring_service import monitoring_service
from utils.logger import get_logger

logger = get_logger(__name__)

async def test_workflow_compilation():
    """Test que le workflow se compile correctement."""
    logger.info("🧪 Test de compilation du workflow")
    
    try:
        # Créer le graphe
        workflow_graph = create_workflow_graph()
        logger.info("✅ Graphe créé avec succès")
        
        # Compiler le graphe
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        compiled_graph = workflow_graph.compile(checkpointer=checkpointer)
        logger.info("✅ Graphe compilé avec succès")
        
        # Vérifier que la méthode astream existe
        if hasattr(compiled_graph, 'astream'):
            logger.info("✅ Méthode astream disponible")
            return True
        else:
            logger.error("❌ Méthode astream manquante")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erreur de compilation: {e}")
        return False

async def test_monitoring_startup():
    """Test que le monitoring démarre correctement."""
    logger.info("🧪 Test de démarrage du monitoring")
    
    try:
        # Arrêter le monitoring s'il est actif
        if monitoring_service.is_monitoring_active:
            await monitoring_service.stop_monitoring()
        
        # Démarrer le monitoring
        await monitoring_service.start_monitoring()
        
        # Vérifier qu'il est actif
        if monitoring_service.is_monitoring_active:
            logger.info("✅ Monitoring actif")
            
            # Vérifier les tâches en arrière-plan
            active_tasks = sum(1 for task in monitoring_service.background_tasks if not task.done())
            logger.info(f"✅ {active_tasks} tâches de monitoring actives")
            
            return active_tasks > 0
        else:
            logger.error("❌ Monitoring non actif")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erreur monitoring: {e}")
        return False

async def test_workflow_state_creation():
    """Test de création d'état de workflow."""
    logger.info("🧪 Test de création d'état workflow")
    
    try:
        # Créer une tâche de test
        task_request = TaskRequest(
            task_id="test_123",
            title="Test workflow fixes",
            description="Test de correction",
            priority="medium"
        )
        
        # Tester la création d'état initial
        from graph.workflow_graph import _create_initial_state_with_recovery
        initial_state = _create_initial_state_with_recovery(task_request, "test_workflow", 1, "test_uuid")
        
        if isinstance(initial_state, dict) and "task" in initial_state:
            logger.info("✅ État initial créé correctement")
            return True
        else:
            logger.error("❌ État initial invalide")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erreur création état: {e}")
        return False

async def main():
    """Test principal."""
    logger.info("🚀 Tests de correction du workflow")
    
    tests = [
        ("Compilation workflow", test_workflow_compilation),
        ("Démarrage monitoring", test_monitoring_startup),
        ("Création état workflow", test_workflow_state_creation),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
            status = "✅ PASSÉ" if result else "❌ ÉCHOUÉ"
            logger.info(f"{status} - {test_name}")
        except Exception as e:
            logger.error(f"💥 ERREUR - {test_name}: {e}")
            results.append((test_name, False))
    
    # Résumé
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    logger.info(f"\n📊 Résultats: {passed}/{total} tests réussis")
    
    if passed == total:
        logger.info("🎉 Toutes les corrections fonctionnent !")
    else:
        logger.warning("⚠️ Certaines corrections nécessitent encore du travail")
    
    # Nettoyer
    try:
        if monitoring_service.is_monitoring_active:
            await monitoring_service.stop_monitoring()
    except:
        pass
    
    return passed == total

if __name__ == "__main__":
    asyncio.run(main()) 