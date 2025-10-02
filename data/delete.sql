-- 1. Supprimer les données des tables enfants d'abord
DELETE FROM run_steps;
DELETE FROM ai_code_generations;
DELETE FROM test_results;
DELETE FROM pull_requests;
DELETE FROM task_runs;
DELETE FROM performance_metrics;
DELETE FROM application_logs;

DELETE FROM webhook_events;

DELETE FROM system_config;

DELETE FROM tasks;


-- Vérifier que toutes les tables sont vides
DO $$ 
DECLARE
    table_name text;
    row_count bigint;
BEGIN
    FOR table_name IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename IN (
            'tasks', 'task_runs', 'run_steps', 'ai_interactions',
            'ai_code_generations', 'test_results', 'pull_requests',
            'webhook_events', 'application_logs', 'performance_metrics',
            'system_config'
        )
    LOOP
        EXECUTE format('SELECT COUNT(*) FROM %I', table_name) INTO row_count;
        RAISE NOTICE 'Table %: % lignes', table_name, row_count;
    END LOOP;
    
    RAISE NOTICE 'Suppression des données terminée';
END $$;