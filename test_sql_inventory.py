# -*- coding: utf-8 -*-
"""
Test d'inventaire SQL - Verification des tables, vues et fonctions utilisees.
Ce script teste la presence et l'utilisation des objets SQL dans le projet.
"""

import asyncio
import asyncpg
from typing import Dict, List, Any
from config.settings import get_settings

settings = get_settings()


async def test_core_tables_exist(conn):
    """Verifie que les tables principales existent."""
    core_tables = [
        'tasks',
        'task_runs',
        'run_steps',
        'run_step_checkpoints',
        'ai_interactions',
        'ai_code_generations',
        'test_results',
        'pull_requests',
        'webhook_events',
        'application_logs',
        'performance_metrics',
        'system_config'
    ]
    
    results = {"passed": 0, "failed": 0, "details": []}
    
    for table in core_tables:
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = $1
            )
        """, table)
        if result:
            results["passed"] += 1
            results["details"].append(f"✅ Table {table} existe")
        else:
            results["failed"] += 1
            results["details"].append(f"❌ Table {table} n'existe pas")
    
    return results


async def test_human_validation_tables_exist(conn):
    """Verifie que les tables de validation humaine existent."""
    validation_tables = [
        'human_validations',
        'human_validation_responses',
        'validation_actions'
    ]
    
    results = {"passed": 0, "failed": 0, "details": []}
    
    for table in validation_tables:
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = $1
            )
        """, table)
        if result:
            results["passed"] += 1
            results["details"].append(f"✅ Table {table} existe")
        else:
            results["failed"] += 1
            results["details"].append(f"❌ Table {table} n'existe pas")
    
    return results


async def test_ai_cost_tracking_table_exists(conn):
    """Verifie que la table de tracking des couts IA existe."""
    results = {"passed": 0, "failed": 0, "details": []}
    
    result = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'ai_usage_logs'
        )
    """)
    if result:
        results["passed"] += 1
        results["details"].append("✅ Table ai_usage_logs existe")
    else:
        results["failed"] += 1
        results["details"].append("❌ Table ai_usage_logs n'existe pas")
    
    return results


async def test_materialized_views_exist(conn):
    """Verifie que les vues materialisees existent."""
    materialized_views = [
        'mv_dashboard_summary',
        'mv_dashboard_stats',
        'mv_realtime_monitoring',
        'mv_cost_analysis',
        'mv_workflow_status',
        'mv_ai_efficiency',
        'mv_code_quality',
        'mv_integration_health',
        'mv_executive_dashboard'
    ]
    
    results = {"passed": 0, "failed": 0, "details": []}
    
    for view in materialized_views:
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_matviews 
                WHERE schemaname = 'public' 
                AND matviewname = $1
            )
        """, view)
        if result:
            results["passed"] += 1
            results["details"].append(f"✅ Vue materialisee {view} existe")
        else:
            results["failed"] += 1
            results["details"].append(f"⚠️  Vue materialisee {view} n'existe pas")
    
    return results


async def test_regular_views_exist(conn):
    """Verifie que les vues regulieres existent."""
    regular_views = [
        'dashboard_summary',
        'performance_dashboard',
        'validation_dashboard',
        'validation_history',
        'ai_cost_daily_summary',
        'ai_cost_by_workflow'
    ]
    
    results = {"passed": 0, "failed": 0, "details": []}
    
    for view in regular_views:
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.views 
                WHERE table_schema = 'public' 
                AND table_name = $1
            )
        """, view)
        if result:
            results["passed"] += 1
            results["details"].append(f"✅ Vue {view} existe")
        else:
            results["failed"] += 1
            results["details"].append(f"⚠️  Vue {view} n'existe pas")
    
    return results


async def test_critical_functions_exist(conn):
    """Verifie que les fonctions critiques existent."""
    critical_functions = [
        'cleanup_old_logs',
        'validate_status_transition',
        'sync_task_last_run',
        'calculate_duration',
        'sync_task_status',
        'mark_expired_validations',
        'get_validation_stats',
        'health_check',
        'optimize_database',
        'refresh_critical_views',
        'refresh_analytics_views'
    ]
    
    results = {"passed": 0, "failed": 0, "details": []}
    
    for func in critical_functions:
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_proc p
                JOIN pg_namespace n ON p.pronamespace = n.oid
                WHERE n.nspname = 'public' 
                AND p.proname = $1
            )
        """, func)
        if result:
            results["passed"] += 1
            results["details"].append(f"✅ Fonction {func} existe")
        else:
            results["failed"] += 1
            results["details"].append(f"⚠️  Fonction {func} n'existe pas")
    
    return results


async def test_triggers_exist(conn):
    """Verifie que les triggers critiques existent."""
    critical_triggers = [
        ('tasks', 'touch_tasks_updated_at'),
        ('tasks', 'tr_validate_task_status'),
        ('tasks', 'tr_log_task_changes'),
        ('task_runs', 'tr_sync_task_last_run'),
        ('task_runs', 'tr_calculate_run_duration'),
        ('task_runs', 'tr_sync_task_status'),
        ('task_runs', 'tr_auto_cleanup'),
        ('run_steps', 'tr_calculate_step_duration'),
        ('human_validation_responses', 'sync_validation_status_trigger'),
        ('system_config', 'touch_system_config_updated_at')
    ]
    
    results = {"passed": 0, "failed": 0, "details": []}
    
    for table_name, trigger_name in critical_triggers:
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_trigger t
                JOIN pg_class c ON t.tgrelid = c.oid
                WHERE c.relname = $1 
                AND t.tgname = $2
            )
        """, table_name, trigger_name)
        if result:
            results["passed"] += 1
            results["details"].append(f"✅ Trigger {trigger_name} sur {table_name}")
        else:
            results["failed"] += 1
            results["details"].append(f"⚠️  Trigger {trigger_name} sur {table_name} absent")
    
    return results


async def test_indexes_on_core_tables(conn):
    """Verifie que les index critiques existent."""
    critical_indexes = [
        ('tasks', 'idx_tasks_monday_item_id'),
        ('tasks', 'idx_tasks_internal_status_partial'),
        ('task_runs', 'idx_task_runs_celery'),
        ('task_runs', 'idx_task_runs_status'),
        ('run_steps', 'idx_run_steps_task_run'),
        ('run_step_checkpoints', 'idx_checkpoints_step_id'),
        ('human_validations', 'idx_human_validations_validation_id'),
        ('human_validations', 'idx_human_validations_status'),
        ('ai_usage_logs', 'ai_usage_logs_workflow_id_idx')
    ]
    
    results = {"passed": 0, "failed": 0, "details": []}
    
    for table_name, index_name in critical_indexes:
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_indexes 
                WHERE schemaname = 'public' 
                AND tablename = $1 
                AND indexname = $2
            )
        """, table_name, index_name)
        if result:
            results["passed"] += 1
            results["details"].append(f"✅ Index {index_name} sur {table_name}")
        else:
            results["failed"] += 1
            results["details"].append(f"⚠️  Index {index_name} sur {table_name} absent")
    
    return results


async def test_database_constraints(conn):
    """Verifie que les contraintes importantes existent."""
    constraints = [
        'tasks_internal_status_chk',
        'task_runs_status_chk',
        'run_steps_status_chk',
        'human_validations_status_chk',
        'ai_usage_logs_cost_positive',
        'ai_usage_logs_tokens_positive'
    ]
    
    results = {"passed": 0, "failed": 0, "details": []}
    
    for constraint in constraints:
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.check_constraints 
                WHERE constraint_schema = 'public' 
                AND constraint_name = $1
            )
        """, constraint)
        if result:
            results["passed"] += 1
            results["details"].append(f"✅ Contrainte {constraint}")
        else:
            results["failed"] += 1
            results["details"].append(f"⚠️  Contrainte {constraint} absente")
    
    return results


async def test_webhook_partitions_exist(conn):
    """Verifie que les partitions de webhook_events existent."""
    results = {"passed": 0, "failed": 0, "details": []}
    
    result = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename LIKE 'webhook_events_%'
        )
    """)
    
    if result:
        count = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename LIKE 'webhook_events_%'
        """)
        results["passed"] = count
        results["details"].append(f"✅ {count} partition(s) webhook_events trouvee(s)")
    else:
        results["failed"] = 1
        results["details"].append("⚠️  Aucune partition webhook_events trouvee")
    
    return results


async def run_inventory_tests():
    """Execute tous les tests d'inventaire."""
    print("=" * 80)
    print("🔍 TESTS D'INVENTAIRE SQL - AI-AGENT")
    print("=" * 80)
    
    all_results = {}
    
    try:
        conn = await asyncpg.connect(settings.database_url)
        print(f"✅ Connexion a la base de donnees reussie")
        db_name = settings.database_url.split('/')[-1].split('?')[0]
        print(f"📊 Base de donnees: {db_name}")
        print("=" * 80)
        
        # Test 1: Tables principales
        print("\n📋 TEST 1: Tables principales")
        print("-" * 80)
        result = await test_core_tables_exist(conn)
        all_results["tables_principales"] = result
        for detail in result["details"]:
            print(detail)
        print(f"📊 Resultat: {result['passed']}/{result['passed'] + result['failed']} tables presentes")
        
        # Test 2: Tables de validation humaine
        print("\n📋 TEST 2: Tables de validation humaine")
        print("-" * 80)
        result = await test_human_validation_tables_exist(conn)
        all_results["tables_validation"] = result
        for detail in result["details"]:
            print(detail)
        print(f"📊 Resultat: {result['passed']}/{result['passed'] + result['failed']} tables presentes")
        
        # Test 3: Table de tracking des couts IA
        print("\n📋 TEST 3: Table de tracking des couts IA")
        print("-" * 80)
        result = await test_ai_cost_tracking_table_exists(conn)
        all_results["table_ai_cost"] = result
        for detail in result["details"]:
            print(detail)
        
        # Test 4: Vues materialisees
        print("\n📋 TEST 4: Vues materialisees")
        print("-" * 80)
        result = await test_materialized_views_exist(conn)
        all_results["vues_materialisees"] = result
        for detail in result["details"]:
            print(detail)
        print(f"📊 Resultat: {result['passed']}/{result['passed'] + result['failed']} vues presentes")
        
        # Test 5: Vues regulieres
        print("\n📋 TEST 5: Vues regulieres")
        print("-" * 80)
        result = await test_regular_views_exist(conn)
        all_results["vues_regulieres"] = result
        for detail in result["details"]:
            print(detail)
        print(f"📊 Resultat: {result['passed']}/{result['passed'] + result['failed']} vues presentes")
        
        # Test 6: Fonctions critiques
        print("\n📋 TEST 6: Fonctions critiques")
        print("-" * 80)
        result = await test_critical_functions_exist(conn)
        all_results["fonctions"] = result
        for detail in result["details"]:
            print(detail)
        print(f"📊 Resultat: {result['passed']}/{result['passed'] + result['failed']} fonctions presentes")
        
        # Test 7: Triggers
        print("\n📋 TEST 7: Triggers")
        print("-" * 80)
        result = await test_triggers_exist(conn)
        all_results["triggers"] = result
        for detail in result["details"]:
            print(detail)
        print(f"📊 Resultat: {result['passed']}/{result['passed'] + result['failed']} triggers presents")
        
        # Test 8: Index
        print("\n📋 TEST 8: Index")
        print("-" * 80)
        result = await test_indexes_on_core_tables(conn)
        all_results["indexes"] = result
        for detail in result["details"]:
            print(detail)
        print(f"📊 Resultat: {result['passed']}/{result['passed'] + result['failed']} index presents")
        
        # Test 9: Contraintes
        print("\n📋 TEST 9: Contraintes")
        print("-" * 80)
        result = await test_database_constraints(conn)
        all_results["contraintes"] = result
        for detail in result["details"]:
            print(detail)
        print(f"📊 Resultat: {result['passed']}/{result['passed'] + result['failed']} contraintes presentes")
        
        # Test 10: Partitions webhook
        print("\n📋 TEST 10: Partitions webhook")
        print("-" * 80)
        result = await test_webhook_partitions_exist(conn)
        all_results["partitions"] = result
        for detail in result["details"]:
            print(detail)
        
        await conn.close()
        
        # Resume global
        print("\n" + "=" * 80)
        print("📊 RESUME GLOBAL DES TESTS")
        print("=" * 80)
        
        total_passed = sum(r["passed"] for r in all_results.values())
        total_failed = sum(r["failed"] for r in all_results.values())
        total_tests = total_passed + total_failed
        
        print(f"✅ Tests reussis: {total_passed}/{total_tests}")
        print(f"❌ Tests echoues: {total_failed}/{total_tests}")
        print(f"📈 Taux de reussite: {(total_passed/total_tests*100):.1f}%")
        
        print("\n" + "=" * 80)
        print("✅ TOUS LES TESTS D'INVENTAIRE TERMINES")
        print("=" * 80)
        
        return all_results
        
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    asyncio.run(run_inventory_tests())