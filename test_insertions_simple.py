# -*- coding: utf-8 -*-
"""
Script de test simplifié pour valider les insertions dans toutes les tables.
"""

import asyncio
import asyncpg
from datetime import datetime, timedelta
import os
import json
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()


async def test_database_insertions():
    """Teste les insertions dans toutes les tables."""
    
    # Récupérer l'URL de la base de données depuis les variables d'environnement
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL non définie dans les variables d'environnement")
        print("💡 Vérifiez que le fichier .env contient DATABASE_URL=...")
        return False
    
    print("=" * 80)
    print("🚀 DÉBUT DES TESTS D'INSERTION DANS LA BASE DE DONNÉES")
    print("=" * 80)
    
    try:
        # Créer une connexion à la base de données
        conn = await asyncpg.connect(db_url)
        print("✅ Connexion à la base de données établie")
        
        # Nettoyer les données de test précédentes
        print("\n🧹 Nettoyage des données de test précédentes...")
        await conn.execute("""
            DELETE FROM tasks WHERE monday_item_id = 999888777;
            DELETE FROM system_config WHERE key = 'test.config.key';
        """)
        print("✅ Données de test nettoyées")
        
        test_results = {}
        test_ids = {}
        
        # Test 1: Table tasks
        print("\n📋 Test 1: table tasks")
        try:
            task_id = await conn.fetchval("""
                INSERT INTO tasks (
                    monday_item_id, monday_board_id, title, description,
                    priority, repository_url, repository_name,
                    monday_status, internal_status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING tasks_id
            """,
                999888777,
                123456,
                "Test Task - Database Insertion",
                "Test de création de tâche",
                "high",
                "https://github.com/test/repo",
                "repo",
                "nouveau",
                "pending"
            )
            test_ids['task_id'] = task_id
            print(f"✅ tasks: Task créée avec ID {task_id}")
            test_results['tasks'] = True
        except Exception as e:
            print(f"❌ tasks: Exception - {e}")
            test_results['tasks'] = False
        
        # Test 2: Table task_runs
        print("\n📋 Test 2: table task_runs")
        try:
            run_id = await conn.fetchval("""
                INSERT INTO task_runs (
                    task_id, run_number, status, celery_task_id,
                    ai_provider, current_node, progress_percentage
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING tasks_runs_id
            """,
                test_ids['task_id'],
                1,
                "started",
                f"test_celery_{datetime.now().timestamp()}",
                "claude",
                "prepare_environment",
                0
            )
            test_ids['run_id'] = run_id
            print(f"✅ task_runs: Run créé avec ID {run_id}")
            test_results['task_runs'] = True
        except Exception as e:
            print(f"❌ task_runs: Exception - {e}")
            test_results['task_runs'] = False
        
        # Test 3: Table run_steps
        print("\n📋 Test 3: table run_steps")
        try:
            step_id = await conn.fetchval("""
                INSERT INTO run_steps (
                    task_run_id, node_name, step_order, status,
                    input_data, started_at
                ) VALUES ($1, $2, $3, $4, $5, NOW())
                RETURNING run_steps_id
            """,
                test_ids['run_id'],
                "test_node",
                1,
                "running",
                json.dumps({"test": "data"})
            )
            test_ids['step_id'] = step_id
            
            # Compléter le step
            await conn.execute("""
                UPDATE run_steps
                SET status = $1, completed_at = NOW(), duration_seconds = $2,
                    output_data = $3
                WHERE run_steps_id = $4
            """,
                "completed",
                10,
                json.dumps({"result": "success"}),
                step_id
            )
            print(f"✅ run_steps: Step créé et complété avec ID {step_id}")
            test_results['run_steps'] = True
        except Exception as e:
            print(f"❌ run_steps: Exception - {e}")
            test_results['run_steps'] = False
        
        # Test 4: Table ai_interactions
        print("\n📋 Test 4: table ai_interactions")
        try:
            interaction_id = await conn.fetchval("""
                INSERT INTO ai_interactions (
                    run_step_id, ai_provider, model_name, prompt,
                    response, token_usage, latency_ms
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING ai_interactions_id
            """,
                test_ids['step_id'],
                "claude",
                "claude-3-5-sonnet-20241022",
                "Test prompt",
                "Test response",
                json.dumps({"prompt_tokens": 10, "completion_tokens": 20}),
                1500
            )
            print(f"✅ ai_interactions: Interaction créée avec ID {interaction_id}")
            test_results['ai_interactions'] = True
        except Exception as e:
            print(f"❌ ai_interactions: Exception - {e}")
            test_results['ai_interactions'] = False
        
        # Test 5: Table ai_code_generations
        print("\n📋 Test 5: table ai_code_generations")
        try:
            gen_id = await conn.fetchval("""
                INSERT INTO ai_code_generations (
                    task_run_id, provider, model, generation_type, prompt,
                    generated_code, tokens_used, response_time_ms, cost_estimate,
                    files_modified
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING ai_code_generations_id
            """,
                test_ids['run_id'],
                "claude",
                "claude-3-5-sonnet-20241022",
                "initial",
                "Generate a hello world function",
                "def hello(): print('Hello World')",
                50,
                2000,
                0.002,
                json.dumps(["test.py"])
            )
            print(f"✅ ai_code_generations: Génération créée avec ID {gen_id}")
            test_results['ai_code_generations'] = True
        except Exception as e:
            print(f"❌ ai_code_generations: Exception - {e}")
            test_results['ai_code_generations'] = False
        
        # Test 6: Table test_results
        print("\n📋 Test 6: table test_results")
        try:
            test_id = await conn.fetchval("""
                INSERT INTO test_results (
                    task_run_id, passed, status, tests_total, tests_passed,
                    tests_failed, tests_skipped, coverage_percentage,
                    pytest_report, duration_seconds
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING test_results_id
            """,
                test_ids['run_id'],
                True,
                "passed",
                10,
                10,
                0,
                0,
                85.5,
                json.dumps({"summary": "All tests passed"}),
                30
            )
            print(f"✅ test_results: Résultats de tests créés avec ID {test_id}")
            test_results['test_results'] = True
        except Exception as e:
            print(f"❌ test_results: Exception - {e}")
            test_results['test_results'] = False
        
        # Test 7: Table pull_requests
        print("\n📋 Test 7: table pull_requests")
        try:
            pr_id = await conn.fetchval("""
                INSERT INTO pull_requests (
                    task_id, task_run_id, github_pr_number, github_pr_url,
                    pr_title, pr_description, pr_status, head_sha,
                    base_branch, feature_branch
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING pull_requests_id
            """,
                test_ids['task_id'],
                test_ids['run_id'],
                123,
                "https://github.com/test/repo/pull/123",
                "Test PR",
                "Test description",
                "open",
                "abc123def456",
                "main",
                "test-branch"
            )
            print(f"✅ pull_requests: PR créée avec ID {pr_id}")
            test_results['pull_requests'] = True
        except Exception as e:
            print(f"❌ pull_requests: Exception - {e}")
            test_results['pull_requests'] = False
        
        # Test 8: Table performance_metrics
        print("\n📋 Test 8: table performance_metrics")
        try:
            await conn.execute("""
                INSERT INTO performance_metrics (
                    task_id, task_run_id, total_duration_seconds,
                    ai_processing_time_seconds, testing_time_seconds,
                    total_ai_calls, total_tokens_used, total_ai_cost,
                    test_coverage_final, retry_attempts
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
                test_ids['task_id'],
                test_ids['run_id'],
                300,
                150,
                50,
                5,
                2000,
                0.05,
                85.5,
                0
            )
            
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM performance_metrics 
                WHERE task_id = $1 AND task_run_id = $2
            """, test_ids['task_id'], test_ids['run_id'])
            
            print(f"✅ performance_metrics: Métriques enregistrées ({count} entrée(s))")
            test_results['performance_metrics'] = True
        except Exception as e:
            print(f"❌ performance_metrics: Exception - {e}")
            test_results['performance_metrics'] = False
        
        # Test 9: Table human_validations
        print("\n📋 Test 9: table human_validations")
        try:
            validation_id = f"test_val_{int(datetime.now().timestamp())}"
            await conn.execute("""
                INSERT INTO human_validations (
                    validation_id, task_id, task_run_id, run_step_id,
                    task_title, task_description, original_request,
                    status, generated_code, code_summary, files_modified,
                    implementation_notes, test_results, pr_info,
                    workflow_id, requested_by, created_at, expires_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
            """,
                validation_id,
                test_ids['task_id'],
                test_ids['run_id'],
                test_ids['step_id'],
                "Test Validation",
                "Test description",
                "Create a test file",
                "pending",
                json.dumps({"test.py": "print('hello')"}),
                "Simple test code",
                ["test.py"],
                "Test implementation",
                json.dumps({"passed": True}),
                None,
                "test_workflow",
                "test_script",
                datetime.now(),
                datetime.now() + timedelta(hours=24)
            )
            test_ids['validation_id'] = validation_id
            print(f"✅ human_validations: Validation créée avec ID {validation_id}")
            test_results['human_validations'] = True
        except Exception as e:
            print(f"❌ human_validations: Exception - {e}")
            test_results['human_validations'] = False
        
        # Test 10: Table human_validation_responses
        print("\n📋 Test 10: table human_validation_responses")
        try:
            hv_id = await conn.fetchval("""
                SELECT human_validations_id FROM human_validations
                WHERE validation_id = $1
            """, test_ids['validation_id'])
            
            await conn.execute("""
                INSERT INTO human_validation_responses (
                    human_validation_id, validation_id, response_status,
                    comments, suggested_changes, approval_notes,
                    validated_by, validated_at, should_merge, should_continue_workflow,
                    validation_duration_seconds
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
                hv_id,
                test_ids['validation_id'],
                "approved",
                "Test approval",
                None,
                "Looks good",
                "test_validator",
                datetime.now(),
                True,
                True,
                300
            )
            print(f"✅ human_validation_responses: Réponse créée pour validation {test_ids['validation_id']}")
            test_results['human_validation_responses'] = True
        except Exception as e:
            print(f"❌ human_validation_responses: Exception - {e}")
            test_results['human_validation_responses'] = False
        
        # Test 11: Table validation_actions
        print("\n📋 Test 11: table validation_actions")
        try:
            hv_id = await conn.fetchval("""
                SELECT human_validations_id FROM human_validations
                WHERE validation_id = $1
            """, test_ids['validation_id'])
            
            action_id = await conn.fetchval("""
                INSERT INTO validation_actions (
                    human_validation_id, validation_id, action_type,
                    action_status, action_data, created_at
                ) VALUES ($1, $2, $3, $4, $5, NOW())
                RETURNING validation_actions_id
            """,
                hv_id,
                test_ids['validation_id'],
                "merge_pr",
                "pending",
                json.dumps({"pr_number": 123, "branch": "test-branch"})
            )
            
            # Mettre à jour l'action
            await conn.execute("""
                UPDATE validation_actions
                SET action_status = $2,
                    result_data = $3,
                    merge_commit_hash = $4,
                    merge_commit_url = $5,
                    completed_at = NOW()
                WHERE validation_actions_id = $1
            """,
                action_id,
                "completed",
                json.dumps({"merge_success": True}),
                "abc123",
                "https://github.com/test/repo/commit/abc123"
            )
            print(f"✅ validation_actions: Action créée et mise à jour avec ID {action_id}")
            test_results['validation_actions'] = True
        except Exception as e:
            print(f"❌ validation_actions: Exception - {e}")
            test_results['validation_actions'] = False
        
        # Test 12: Table system_config
        print("\n📋 Test 12: table system_config")
        try:
            # Vérifier si la clé existe déjà
            existing = await conn.fetchval("""
                SELECT system_config_id FROM system_config WHERE key = $1
            """, "test.config.key")
            
            if existing:
                # Mettre à jour
                await conn.execute("""
                    UPDATE system_config
                    SET value = $2,
                        description = $3,
                        config_type = $4,
                        updated_at = NOW(),
                        updated_by = $5
                    WHERE key = $1
                """,
                    "test.config.key",
                    json.dumps({"test": "updated_value", "number": 100}),
                    "Updated test configuration",
                    "application",
                    "test_script"
                )
            else:
                # Créer
                await conn.execute("""
                    INSERT INTO system_config (key, value, description, config_type, updated_by, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
                """,
                    "test.config.key",
                    json.dumps({"test": "value", "number": 42}),
                    "Test configuration",
                    "application",
                    "test_script"
                )
            
            # Vérifier
            config = await conn.fetchrow("""
                SELECT * FROM system_config WHERE key = $1
            """, "test.config.key")
            
            if config:
                print(f"✅ system_config: Configuration créée/mise à jour")
                test_results['system_config'] = True
            else:
                print(f"❌ system_config: Config créée mais non récupérable")
                test_results['system_config'] = False
        except Exception as e:
            print(f"❌ system_config: Exception - {e}")
            test_results['system_config'] = False
        
        # Afficher le résumé
        print("\n" + "=" * 80)
        print("📊 RÉSUMÉ DES TESTS")
        print("=" * 80)
        
        total_tests = len(test_results)
        passed_tests = sum(1 for result in test_results.values() if result)
        failed_tests = total_tests - passed_tests
        
        for table, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} - {table}")
        
        print("=" * 80)
        print(f"Total: {total_tests} | Réussis: {passed_tests} | Échoués: {failed_tests}")
        
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        print(f"Taux de réussite: {success_rate:.1f}%")
        print("=" * 80)
        
        await conn.close()
        
        return passed_tests == total_tests
        
    except Exception as e:
        print(f"💥 ERREUR CRITIQUE: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_database_insertions())
    if result:
        print("\n🎉 TOUS LES TESTS ONT RÉUSSI!")
        exit(0)
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        exit(1)
