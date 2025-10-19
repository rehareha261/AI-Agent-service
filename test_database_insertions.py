#!/usr/bin/env python
"""
Script de test pour valider les insertions dans les tables:
- human_validations
- human_validation_responses  
- test_results

Usage: python test_database_insertions.py
"""
import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import asyncpg
from datetime import datetime, timedelta
from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def test_database_insertions():
    """Test des insertions dans les tables critiques."""
    
    logger.info("🧪 Démarrage des tests d'insertion en base de données")
    
    # Connexion à la base de données
    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name
    )
    
    try:
        # ==========================================
        # TEST 1: Vérifier la structure des tables
        # ==========================================
        logger.info("\n📋 TEST 1: Vérification de la structure des tables")
        
        tables_to_check = ['human_validations', 'human_validation_responses', 'test_results']
        
        for table_name in tables_to_check:
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = $1
                )
            """, table_name)
            
            if exists:
                logger.info(f"  ✅ Table {table_name} existe")
                
                # Compter les enregistrements
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table_name}")
                logger.info(f"     📊 {count} enregistrement(s) dans {table_name}")
            else:
                logger.error(f"  ❌ Table {table_name} n'existe pas!")
        
        # ==========================================
        # TEST 2: Vérifier les dernières insertions
        # ==========================================
        logger.info("\n📋 TEST 2: Vérification des dernières insertions")
        
        # Test human_validations
        recent_validations = await conn.fetch("""
            SELECT 
                validation_id, 
                task_title, 
                status, 
                created_at,
                task_id,
                task_run_id
            FROM human_validations 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        
        if recent_validations:
            logger.info(f"  ✅ {len(recent_validations)} validations récentes trouvées:")
            for val in recent_validations:
                logger.info(f"     - {val['validation_id']}: {val['task_title']} ({val['status']}) - {val['created_at']}")
        else:
            logger.warning("  ⚠️ Aucune validation trouvée dans human_validations")
        
        # Test human_validation_responses
        recent_responses = await conn.fetch("""
            SELECT 
                hvr.validation_id, 
                hvr.response_status, 
                hvr.validated_by,
                hvr.validated_at,
                hv.task_title
            FROM human_validation_responses hvr
            JOIN human_validations hv ON hvr.human_validation_id = hv.human_validations_id
            ORDER BY hvr.validated_at DESC 
            LIMIT 5
        """)
        
        if recent_responses:
            logger.info(f"  ✅ {len(recent_responses)} réponses récentes trouvées:")
            for resp in recent_responses:
                logger.info(f"     - {resp['validation_id']}: {resp['response_status']} par {resp['validated_by']} - {resp['validated_at']}")
        else:
            logger.warning("  ⚠️ Aucune réponse trouvée dans human_validation_responses")
        
        # Test test_results
        recent_tests = await conn.fetch("""
            SELECT 
                tr.test_results_id,
                tr.task_run_id, 
                tr.passed, 
                tr.status,
                tr.tests_total,
                tr.tests_passed,
                tr.tests_failed,
                tr.executed_at,
                t.title as task_title
            FROM test_results tr
            JOIN task_runs runs ON tr.task_run_id = runs.tasks_runs_id
            JOIN tasks t ON runs.task_id = t.tasks_id
            ORDER BY tr.executed_at DESC 
            LIMIT 5
        """)
        
        if recent_tests:
            logger.info(f"  ✅ {len(recent_tests)} résultats de tests récents trouvés:")
            for test in recent_tests:
                logger.info(f"     - Test {test['test_results_id']} (run {test['task_run_id']}): {test['status']} - "
                          f"{test['tests_passed']}/{test['tests_total']} passés - {test['executed_at']}")
        else:
            logger.warning("  ⚠️ Aucun résultat de test trouvé dans test_results")
        
        # ==========================================
        # TEST 3: Vérifier l'intégrité référentielle
        # ==========================================
        logger.info("\n📋 TEST 3: Vérification de l'intégrité référentielle")
        
        # Vérifier que les validations ont des références valides
        orphan_validations = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM human_validations hv
            LEFT JOIN tasks t ON hv.task_id = t.tasks_id
            WHERE t.tasks_id IS NULL
        """)
        
        if orphan_validations > 0:
            logger.warning(f"  ⚠️ {orphan_validations} validation(s) orpheline(s) (task_id invalide)")
        else:
            logger.info("  ✅ Toutes les validations ont des task_id valides")
        
        # Vérifier que les réponses ont des validations valides
        orphan_responses = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM human_validation_responses hvr
            LEFT JOIN human_validations hv ON hvr.human_validation_id = hv.human_validations_id
            WHERE hv.human_validations_id IS NULL
        """)
        
        if orphan_responses > 0:
            logger.warning(f"  ⚠️ {orphan_responses} réponse(s) orpheline(s)")
        else:
            logger.info("  ✅ Toutes les réponses ont des validations valides")
        
        # Vérifier que les tests ont des task_runs valides
        orphan_tests = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM test_results tr
            LEFT JOIN task_runs runs ON tr.task_run_id = runs.tasks_runs_id
            WHERE runs.tasks_runs_id IS NULL
        """)
        
        if orphan_tests > 0:
            logger.warning(f"  ⚠️ {orphan_tests} test(s) orphelin(s)")
        else:
            logger.info("  ✅ Tous les tests ont des task_run_id valides")
        
        # ==========================================
        # TEST 4: Statistiques globales
        # ==========================================
        logger.info("\n📋 TEST 4: Statistiques globales")
        
        stats = await conn.fetchrow("""
            SELECT 
                (SELECT COUNT(*) FROM human_validations) as total_validations,
                (SELECT COUNT(*) FROM human_validations WHERE status = 'pending') as pending_validations,
                (SELECT COUNT(*) FROM human_validations WHERE status = 'approved') as approved_validations,
                (SELECT COUNT(*) FROM human_validations WHERE status = 'rejected') as rejected_validations,
                (SELECT COUNT(*) FROM human_validation_responses) as total_responses,
                (SELECT COUNT(*) FROM test_results) as total_tests,
                (SELECT COUNT(*) FROM test_results WHERE passed = true) as passed_tests,
                (SELECT COUNT(*) FROM test_results WHERE passed = false) as failed_tests
        """)
        
        logger.info(f"\n  📊 Statistiques:")
        logger.info(f"     Validations:")
        logger.info(f"       - Total: {stats['total_validations']}")
        logger.info(f"       - En attente: {stats['pending_validations']}")
        logger.info(f"       - Approuvées: {stats['approved_validations']}")
        logger.info(f"       - Rejetées: {stats['rejected_validations']}")
        logger.info(f"     Réponses: {stats['total_responses']}")
        logger.info(f"     Tests:")
        logger.info(f"       - Total: {stats['total_tests']}")
        logger.info(f"       - Réussis: {stats['passed_tests']}")
        logger.info(f"       - Échoués: {stats['failed_tests']}")
        
        # ==========================================
        # TEST 5: Vérifier les workflows récents
        # ==========================================
        logger.info("\n📋 TEST 5: Vérification des workflows récents")
        
        recent_workflows = await conn.fetch("""
            SELECT 
                t.tasks_id,
                t.title,
                t.status as task_status,
                tr.tasks_runs_id,
                tr.status as run_status,
                tr.started_at,
                tr.completed_at,
                (SELECT COUNT(*) FROM human_validations hv WHERE hv.task_id = t.tasks_id) as validation_count,
                (SELECT COUNT(*) FROM test_results test WHERE test.task_run_id = tr.tasks_runs_id) as test_count
            FROM tasks t
            LEFT JOIN task_runs tr ON t.tasks_id = tr.task_id
            WHERE t.created_at > NOW() - INTERVAL '24 hours'
            ORDER BY t.created_at DESC
            LIMIT 10
        """)
        
        if recent_workflows:
            logger.info(f"  ✅ {len(recent_workflows)} workflows des dernières 24h:")
            for wf in recent_workflows:
                logger.info(f"     - Task {wf['tasks_id']}: {wf['title']}")
                logger.info(f"       Status: {wf['task_status']} | Run: {wf['run_status']}")
                logger.info(f"       Validations: {wf['validation_count']} | Tests: {wf['test_count']}")
        else:
            logger.warning("  ⚠️ Aucun workflow trouvé dans les dernières 24h")
        
        # ==========================================
        # RÉSUMÉ FINAL
        # ==========================================
        logger.info("\n" + "="*60)
        logger.info("📊 RÉSUMÉ FINAL")
        logger.info("="*60)
        
        issues_found = []
        
        if stats['total_validations'] == 0:
            issues_found.append("Aucune validation trouvée dans human_validations")
        
        if stats['total_responses'] == 0:
            issues_found.append("Aucune réponse trouvée dans human_validation_responses")
        
        if stats['total_tests'] == 0:
            issues_found.append("Aucun test trouvé dans test_results")
        
        if orphan_validations > 0:
            issues_found.append(f"{orphan_validations} validation(s) avec task_id invalide")
        
        if orphan_responses > 0:
            issues_found.append(f"{orphan_responses} réponse(s) orpheline(s)")
        
        if orphan_tests > 0:
            issues_found.append(f"{orphan_tests} test(s) orphelin(s)")
        
        if issues_found:
            logger.warning(f"\n⚠️  {len(issues_found)} problème(s) détecté(s):")
            for issue in issues_found:
                logger.warning(f"  - {issue}")
        else:
            logger.info("\n✅ Aucun problème détecté! Toutes les tables sont correctement alimentées.")
        
        return len(issues_found) == 0
        
    finally:
        await conn.close()


if __name__ == "__main__":
    success = asyncio.run(test_database_insertions())
    
    if success:
        logger.info("\n✅ Tests terminés avec succès!")
        exit(0)
    else:
        logger.warning("\n⚠️ Tests terminés avec des avertissements")
        exit(1)
