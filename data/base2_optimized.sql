-- =========================================
-- CORRECTIONS ET AMÉLIORATIONS CRITIQUES
-- =========================================

-- 1. CORRECTION : Références FK incorrectes
-- Dans le schéma original, plusieurs FK pointent vers des colonnes inexistantes
ALTER TABLE task_runs DROP CONSTRAINT IF EXISTS task_runs_task_id_fkey;
ALTER TABLE task_runs ADD CONSTRAINT task_runs_task_id_fkey 
    FOREIGN KEY (task_id) REFERENCES tasks(tasks_id) ON DELETE CASCADE;

-- Correction pour tous les autres FK
ALTER TABLE run_steps DROP CONSTRAINT IF EXISTS run_steps_task_run_id_fkey;
ALTER TABLE run_steps ADD CONSTRAINT run_steps_task_run_id_fkey 
    FOREIGN KEY (task_run_id) REFERENCES task_runs(tasks_runs_id) ON DELETE CASCADE;

-- Idem pour les autres tables...

-- 2. TRIGGERS MANQUANTS CRITIQUES
-- =========================================

-- A. Trigger pour synchroniser last_run_id dans tasks
CREATE OR REPLACE FUNCTION sync_task_last_run() RETURNS TRIGGER AS $$
BEGIN
    UPDATE tasks 
    SET last_run_id = NEW.tasks_runs_id,
        updated_at = NOW()
    WHERE tasks_id = NEW.task_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER tr_sync_task_last_run
    AFTER INSERT OR UPDATE ON task_runs
    FOR EACH ROW 
    EXECUTE FUNCTION sync_task_last_run();

-- B. Trigger pour calculer la durée automatiquement
CREATE OR REPLACE FUNCTION calculate_duration() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.completed_at IS NOT NULL AND OLD.completed_at IS NULL THEN
        NEW.duration_seconds = EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at))::INTEGER;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Appliquer sur task_runs et run_steps
CREATE OR REPLACE TRIGGER tr_calculate_run_duration
    BEFORE UPDATE ON task_runs
    FOR EACH ROW 
    EXECUTE FUNCTION calculate_duration();

CREATE OR REPLACE TRIGGER tr_calculate_step_duration
    BEFORE UPDATE ON run_steps
    FOR EACH ROW 
    EXECUTE FUNCTION calculate_duration();

-- C. Trigger pour mettre à jour le statut des tâches selon les runs
CREATE OR REPLACE FUNCTION sync_task_status() RETURNS TRIGGER AS $$
BEGIN
    -- Si le run est completed, marquer la tâche comme completed
    IF NEW.status = 'completed' AND (OLD.status IS NULL OR OLD.status != 'completed') THEN
        UPDATE tasks 
        SET internal_status = 'completed',
            completed_at = NEW.completed_at,
            updated_at = NOW()
        WHERE tasks_id = NEW.task_id;
    
    -- Si le run a failed et c'est le dernier run, marquer failed
    ELSIF NEW.status = 'failed' THEN
        UPDATE tasks 
        SET internal_status = 'failed',
            updated_at = NOW()
        WHERE tasks_id = NEW.task_id
          AND last_run_id = NEW.tasks_runs_id;
    
    -- Si le run démarre, marquer processing
    ELSIF NEW.status = 'running' AND (OLD.status IS NULL OR OLD.status = 'started') THEN
        UPDATE tasks 
        SET internal_status = 'processing',
            started_at = COALESCE(started_at, NEW.started_at),
            updated_at = NOW()
        WHERE tasks_id = NEW.task_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER tr_sync_task_status
    AFTER UPDATE ON task_runs
    FOR EACH ROW 
    EXECUTE FUNCTION sync_task_status();

-- 3. TRIGGERS DE VALIDATION
-- =========================================

-- Validation des transitions de statut
CREATE OR REPLACE FUNCTION validate_status_transition() RETURNS TRIGGER AS $$
DECLARE
    valid_transitions JSONB := '{
        "pending": ["processing", "failed"],
        "processing": ["testing", "debugging", "completed", "failed"],
        "testing": ["quality_check", "debugging", "completed", "failed"],
        "debugging": ["testing", "completed", "failed"],
        "quality_check": ["completed", "failed"],
        "completed": [],
        "failed": ["pending", "processing"]
    }'::JSONB;
BEGIN
    IF OLD.internal_status IS NOT NULL AND 
       NOT (valid_transitions->OLD.internal_status ? NEW.internal_status) THEN
        RAISE EXCEPTION 'Invalid status transition from % to %', 
            OLD.internal_status, NEW.internal_status;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER tr_validate_task_status
    BEFORE UPDATE ON tasks
    FOR EACH ROW 
    EXECUTE FUNCTION validate_status_transition();

-- 4. TRIGGERS D'AUDIT ET LOGGING
-- =========================================

-- Log automatique des changements critiques
CREATE OR REPLACE FUNCTION log_critical_changes() RETURNS TRIGGER AS $$
BEGIN
    -- Log changement de statut de tâche
    IF TG_TABLE_NAME = 'tasks' AND OLD.internal_status != NEW.internal_status THEN
        INSERT INTO application_logs (
            task_id, level, source_component, action, message, metadata
        ) VALUES (
            NEW.tasks_id, 'INFO', 'trigger', 'status_change',
            format('Task status changed from %s to %s', OLD.internal_status, NEW.internal_status),
            jsonb_build_object(
                'old_status', OLD.internal_status,
                'new_status', NEW.internal_status,
                'task_title', NEW.title
            )
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER tr_log_task_changes
    AFTER UPDATE ON tasks
    FOR EACH ROW 
    EXECUTE FUNCTION log_critical_changes();

-- 5. TRIGGERS DE MAINTENANCE AUTOMATIQUE
-- =========================================

-- Nettoyage automatique après completion
CREATE OR REPLACE FUNCTION auto_cleanup() RETURNS TRIGGER AS $$
BEGIN
    -- Nettoyer les anciens runs si plus de 10 pour cette tâche
    IF NEW.status = 'completed' THEN
        DELETE FROM task_runs 
        WHERE task_id = NEW.task_id 
          AND status IN ('completed', 'failed')
          AND tasks_runs_id NOT IN (
              SELECT tasks_runs_id FROM task_runs 
              WHERE task_id = NEW.task_id 
              ORDER BY started_at DESC 
              LIMIT 10
          );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER tr_auto_cleanup
    AFTER UPDATE ON task_runs
    FOR EACH ROW 
    EXECUTE FUNCTION auto_cleanup();

-- 6. INDEX SUPPLÉMENTAIRES RECOMMANDÉS
-- =========================================

-- Index composites pour les requêtes communes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tasks_status_priority 
    ON tasks(internal_status, priority, created_at DESC) 
    WHERE internal_status IN ('pending', 'processing');

-- Index pour les dashboards
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tasks_created_status 
    ON tasks(DATE_TRUNC('day', created_at), internal_status);

-- Index pour les métriques de performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_perf_metrics_date_cost 
    ON performance_metrics(DATE_TRUNC('day', recorded_at), total_ai_cost);

-- Index partiel pour les webhooks non traités
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhook_unprocessed 
    ON webhook_events(received_at DESC) 
    WHERE processed = FALSE;

-- 7. VUES MATÉRIALISÉES SUPPLÉMENTAIRES
-- =========================================

-- Vue pour monitoring en temps réel
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_realtime_monitoring AS
SELECT 
    internal_status,
    COUNT(*) as count,
    AVG(EXTRACT(EPOCH FROM (NOW() - started_at))/60) as avg_minutes_since_start
FROM tasks 
WHERE internal_status IN ('pending', 'processing', 'testing', 'debugging')
GROUP BY internal_status;

CREATE UNIQUE INDEX ON mv_realtime_monitoring(internal_status);

-- Vue pour l'analyse des coûts
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_cost_analysis AS
SELECT 
    DATE_TRUNC('day', recorded_at) as day,
    ai_provider,
    model_name,
    SUM(total_ai_cost) as daily_cost,
    COUNT(*) as runs_count,
    AVG(total_tokens_used) as avg_tokens
FROM performance_metrics pm
JOIN task_runs tr ON tr.tasks_runs_id = pm.task_run_id
WHERE recorded_at >= NOW() - INTERVAL '30 days'
GROUP BY 1, 2, 3;

CREATE UNIQUE INDEX ON mv_cost_analysis(day, ai_provider, model_name);

-- 8. FONCTION D'OPTIMISATION AVANCÉE
-- =========================================

CREATE OR REPLACE FUNCTION optimize_database() RETURNS void AS $$
DECLARE
    table_name TEXT;
    index_name TEXT;
BEGIN
    -- Mise à jour des statistiques pour toutes les tables principales
    FOR table_name IN 
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename IN ('tasks', 'task_runs', 'run_steps', 'ai_interactions')
    LOOP
        EXECUTE format('ANALYZE %I', table_name);
    END LOOP;
    
    -- Refresh des vues matérialisées
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_dashboard_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_realtime_monitoring;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_cost_analysis;
    
    -- Log de l'optimisation
    INSERT INTO application_logs (level, source_component, action, message)
    VALUES ('INFO', 'maintenance', 'optimize_database', 'Database optimization completed');
    
END;
$$ LANGUAGE plpgsql;

-- 9. CONSTRAINTS SUPPLÉMENTAIRES POUR L'INTÉGRITÉ
-- =========================================

-- S'assurer qu'une tâche completed a bien un completed_at
ALTER TABLE tasks ADD CONSTRAINT tasks_completed_consistency 
    CHECK (
        (internal_status = 'completed' AND completed_at IS NOT NULL) OR
        (internal_status != 'completed')
    );

-- S'assurer que la progression est cohérente
ALTER TABLE task_runs ADD CONSTRAINT runs_progress_consistency 
    CHECK (
        progress_percentage BETWEEN 0 AND 100 AND
        (status = 'completed' AND progress_percentage = 100) OR
        (status != 'completed')
    );

-- 10. FONCTION DE MONITORING DE LA SANTÉ DE LA DB
-- =========================================

CREATE OR REPLACE FUNCTION health_check() RETURNS TABLE(
    metric_name TEXT,
    metric_value NUMERIC,
    status TEXT
) AS $$
BEGIN
    -- Tâches en attente trop longtemps
    RETURN QUERY
    SELECT 
        'pending_tasks_old' as metric_name,
        COUNT(*)::NUMERIC as metric_value,
        CASE WHEN COUNT(*) > 100 THEN 'WARNING' ELSE 'OK' END as status
    FROM tasks 
    WHERE internal_status = 'pending' 
      AND created_at < NOW() - INTERVAL '1 hour';
    
    -- Utilisation de l'espace disque
    RETURN QUERY
    SELECT 
        'database_size_mb' as metric_name,
        pg_database_size(current_database())::NUMERIC / 1024 / 1024 as metric_value,
        'INFO' as status;
    
    -- Taux de succès des 24 dernières heures
    RETURN QUERY
    SELECT 
        'success_rate_24h' as metric_name,
        (COUNT(*) FILTER (WHERE tr.status = 'completed')::NUMERIC / NULLIF(COUNT(*), 0) * 100) as metric_value,
        CASE 
            WHEN (COUNT(*) FILTER (WHERE tr.status = 'completed')::NUMERIC / NULLIF(COUNT(*), 0) * 100) < 80 
            THEN 'WARNING' 
            ELSE 'OK' 
        END as status
    FROM tasks t
    LEFT JOIN task_runs tr ON tr.task_id = t.tasks_id AND tr.tasks_runs_id = t.last_run_id
    WHERE t.created_at >= NOW() - INTERVAL '24 hours';
    
END;
$$ LANGUAGE plpgsql;

-- Exemple d'utilisation: SELECT * FROM health_check();