-- Extension pour UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================
-- TABLES PRINCIPALES
-- =============================================

-- Table des projets GitHub
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    github_repository_url TEXT NOT NULL,
    github_repository_name VARCHAR(255) NOT NULL,
    github_owner VARCHAR(255) NOT NULL,
    monday_board_id BIGINT,
    default_branch VARCHAR(100) DEFAULT 'main',
    programming_language VARCHAR(50),
    framework VARCHAR(100),
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_github_repo UNIQUE(github_owner, github_repository_name)
);

-- Table des tâches Monday.com
CREATE TABLE monday_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    monday_item_id BIGINT NOT NULL UNIQUE,
    monday_board_id BIGINT NOT NULL,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(100) NOT NULL,
    priority VARCHAR(50),
    assignee VARCHAR(255),
    labels TEXT[], -- Array pour stocker les labels
    due_date TIMESTAMP WITH TIME ZONE,
    monday_created_at TIMESTAMP WITH TIME ZONE,
    monday_updated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_monday_tasks_item_id (monday_item_id),
    INDEX idx_monday_tasks_project_id (project_id),
    INDEX idx_monday_tasks_status (status)
);

-- Table des exécutions de workflow (jobs Celery)
CREATE TABLE workflow_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    celery_task_id VARCHAR(255) UNIQUE,
    monday_task_id UUID REFERENCES monday_tasks(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, running, completed, failed, cancelled
    workflow_type VARCHAR(100) DEFAULT 'full_development_cycle',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    error_message TEXT,
    metadata JSONB, -- Pour stocker des informations flexibles
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_workflow_executions_celery_id (celery_task_id),
    INDEX idx_workflow_executions_monday_task (monday_task_id),
    INDEX idx_workflow_executions_status (status),
    INDEX idx_workflow_executions_started_at (started_at)
);

-- Table des étapes de workflow LangGraph
CREATE TABLE workflow_steps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_execution_id UUID REFERENCES workflow_executions(id) ON DELETE CASCADE,
    step_name VARCHAR(255) NOT NULL, -- prepare_environment_enhanced, analyze_requirements, etc.
    step_order INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, running, completed, failed, skipped
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    ai_provider VARCHAR(50), -- claude, openai, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_workflow_steps_execution_id (workflow_execution_id),
    INDEX idx_workflow_steps_name (step_name),
    INDEX idx_workflow_steps_status (status)
);

-- Table des providers AI et leur utilisation
CREATE TABLE ai_providers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    api_endpoint TEXT,
    model_name VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    rate_limit_per_minute INTEGER,
    cost_per_1k_tokens DECIMAL(8,6),
    capabilities TEXT[], -- Array des capacités : coding, analysis, debugging, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table des utilisations des providers AI
CREATE TABLE ai_usage_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_step_id UUID REFERENCES workflow_steps(id) ON DELETE CASCADE,
    ai_provider_id UUID REFERENCES ai_providers(id) ON DELETE CASCADE,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    cost DECIMAL(10,6),
    response_time_ms INTEGER,
    model_used VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_ai_usage_logs_step_id (workflow_step_id),
    INDEX idx_ai_usage_logs_provider_id (ai_provider_id),
    INDEX idx_ai_usage_logs_created_at (created_at)
);

-- Table des tests et résultats
CREATE TABLE test_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_step_id UUID REFERENCES workflow_steps(id) ON DELETE CASCADE,
    test_type VARCHAR(100) NOT NULL, -- unit, integration, security, coverage, linting
    test_framework VARCHAR(100), -- pytest, coverage, bandit, flake8, etc.
    status VARCHAR(50) NOT NULL, -- passed, failed, error, skipped
    total_tests INTEGER,
    passed_tests INTEGER,
    failed_tests INTEGER,
    skipped_tests INTEGER,
    coverage_percentage DECIMAL(5,2),
    execution_time_seconds DECIMAL(10,3),
    test_output TEXT,
    error_details TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_test_executions_step_id (workflow_step_id),
    INDEX idx_test_executions_type (test_type),
    INDEX idx_test_executions_status (status)
);

-- Table des Pull Requests GitHub
CREATE TABLE github_pull_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_execution_id UUID REFERENCES workflow_executions(id) ON DELETE CASCADE,
    github_pr_number INTEGER NOT NULL,
    github_pr_id BIGINT NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL, -- open, closed, merged, draft
    head_branch VARCHAR(255) NOT NULL,
    base_branch VARCHAR(255) NOT NULL,
    files_changed INTEGER,
    additions INTEGER,
    deletions INTEGER,
    github_created_at TIMESTAMP WITH TIME ZONE,
    github_updated_at TIMESTAMP WITH TIME ZONE,
    github_merged_at TIMESTAMP WITH TIME ZONE,
    github_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_github_prs_workflow_id (workflow_execution_id),
    INDEX idx_github_prs_status (status),
    INDEX idx_github_prs_number (github_pr_number)
);

-- Table des logs système
CREATE TABLE system_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    level VARCHAR(20) NOT NULL, -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    source VARCHAR(100) NOT NULL, -- fastapi, celery, langgraph, webhook, etc.
    workflow_execution_id UUID REFERENCES workflow_executions(id) ON DELETE CASCADE,
    workflow_step_id UUID REFERENCES workflow_steps(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    context JSONB, -- Données contextuelles flexibles
    stack_trace TEXT,
    user_id VARCHAR(255),
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_system_logs_level (level),
    INDEX idx_system_logs_source (source),
    INDEX idx_system_logs_workflow_execution (workflow_execution_id),
    INDEX idx_system_logs_created_at (created_at)
);

-- Table des webhooks Monday.com
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    webhook_id VARCHAR(255),
    event_type VARCHAR(100) NOT NULL,
    monday_board_id BIGINT,
    monday_item_id BIGINT,
    raw_payload JSONB NOT NULL,
    signature VARCHAR(255),
    is_valid_signature BOOLEAN,
    processed BOOLEAN DEFAULT false,
    workflow_execution_id UUID REFERENCES workflow_executions(id),
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    
    INDEX idx_webhook_events_type (event_type),
    INDEX idx_webhook_events_monday_item (monday_item_id),
    INDEX idx_webhook_events_processed (processed),
    INDEX idx_webhook_events_created_at (created_at)
);

-- Table des configurations système
CREATE TABLE system_configurations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key VARCHAR(255) NOT NULL UNIQUE,
    value TEXT NOT NULL,
    description TEXT,
    is_sensitive BOOLEAN DEFAULT false, -- Pour masquer les valeurs sensibles dans l'admin
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- VUES UTILES
-- =============================================

-- Vue des statistiques par projet
CREATE VIEW project_statistics AS
SELECT 
    p.id,
    p.name,
    p.github_repository_name,
    COUNT(DISTINCT mt.id) as total_tasks,
    COUNT(DISTINCT we.id) as total_executions,
    COUNT(CASE WHEN we.status = 'completed' THEN 1 END) as completed_executions,
    COUNT(CASE WHEN we.status = 'failed' THEN 1 END) as failed_executions,
    AVG(we.duration_seconds) as avg_execution_time,
    COUNT(DISTINCT gpr.id) as total_pull_requests,
    COUNT(CASE WHEN gpr.status = 'merged' THEN 1 END) as merged_pull_requests,
    MAX(we.started_at) as last_execution_date
FROM projects p
LEFT JOIN monday_tasks mt ON p.id = mt.project_id
LEFT JOIN workflow_executions we ON mt.id = we.monday_task_id
LEFT JOIN github_pull_requests gpr ON we.id = gpr.workflow_execution_id
GROUP BY p.id, p.name, p.github_repository_name;

-- Vue des performances AI par provider
CREATE VIEW ai_provider_performance AS
SELECT 
    ap.name,
    COUNT(aul.id) as total_requests,
    AVG(aul.response_time_ms) as avg_response_time,
    SUM(aul.total_tokens) as total_tokens_used,
    SUM(aul.cost) as total_cost,
    COUNT(CASE WHEN ws.status = 'completed' THEN 1 END) as successful_steps,
    COUNT(CASE WHEN ws.status = 'failed' THEN 1 END) as failed_steps
FROM ai_providers ap
LEFT JOIN ai_usage_logs aul ON ap.id = aul.ai_provider_id
LEFT JOIN workflow_steps ws ON aul.workflow_step_id = ws.id
GROUP BY ap.id, ap.name;

-- =============================================
-- FONCTIONS ET TRIGGERS
-- =============================================

-- Fonction pour mettre à jour updated_at automatiquement
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers pour updated_at
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_monday_tasks_updated_at BEFORE UPDATE ON monday_tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ai_providers_updated_at BEFORE UPDATE ON ai_providers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_system_configurations_updated_at BEFORE UPDATE ON system_configurations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================
-- DONNÉES INITIALES
-- =============================================

-- Insertion des providers AI par défaut
INSERT INTO ai_providers (name, api_endpoint, model_name, rate_limit_per_minute, cost_per_1k_tokens, capabilities) VALUES
('Claude', 'https://api.anthropic.com/v1', 'claude-3-5-sonnet-20241022', 100, 0.003, ARRAY['coding', 'analysis', 'debugging', 'documentation']),
('OpenAI', 'https://api.openai.com/v1', 'gpt-4', 60, 0.03, ARRAY['coding', 'analysis', 'debugging', 'documentation']),
('OpenAI-3.5', 'https://api.openai.com/v1', 'gpt-3.5-turbo', 200, 0.0015, ARRAY['coding', 'simple_analysis']);

-- Configurations système par défaut
INSERT INTO system_configurations (key, value, description, is_sensitive) VALUES
('webhook_secret', 'your_webhook_secret_here', 'Secret pour valider les webhooks Monday.com', true),
('github_token', 'your_github_token_here', 'Token GitHub pour les API calls', true),
('max_retry_attempts', '3', 'Nombre maximum de tentatives pour une étape échouée', false),
('default_test_timeout', '300', 'Timeout par défaut pour les tests (en secondes)', false),
('cleanup_logs_days', '30', 'Nombre de jours avant nettoyage des logs', false);

-- =============================================
-- INDEXES SUPPLÉMENTAIRES POUR PERFORMANCE
-- =============================================

-- Index composites pour les requêtes courantes
CREATE INDEX idx_workflow_executions_project_status ON workflow_executions(project_id, status);
CREATE INDEX idx_workflow_steps_execution_order ON workflow_steps(workflow_execution_id, step_order);
CREATE INDEX idx_test_executions_type_status ON test_executions(test_type, status);
CREATE INDEX idx_system_logs_level_created_at ON system_logs(level, created_at DESC);
CREATE INDEX idx_ai_usage_logs_provider_created_at ON ai_usage_logs(ai_provider_id, created_at DESC);

-- Index pour les recherches de texte
CREATE INDEX idx_monday_tasks_title_search ON monday_tasks USING gin(to_tsvector('french', title));
CREATE INDEX idx_system_logs_message_search ON system_logs USING gin(to_tsvector('english', message));

-- =============================================
-- COMMENTAIRES SUR LES TABLES
-- =============================================

COMMENT ON TABLE projects IS 'Projets GitHub gérés par le système';
COMMENT ON TABLE monday_tasks IS 'Tâches synchronisées depuis Monday.com';
COMMENT ON TABLE workflow_executions IS 'Exécutions des workflows LangGraph/Celery';
COMMENT ON TABLE workflow_steps IS 'Étapes individuelles des workflows LangGraph';
COMMENT ON TABLE ai_providers IS 'Fournisseurs IA disponibles (Claude, OpenAI, etc.)';
COMMENT ON TABLE ai_usage_logs IS 'Logs d\'utilisation des APIs IA pour facturation et monitoring';
COMMENT ON TABLE test_executions IS 'Résultats des tests automatisés';
COMMENT ON TABLE github_pull_requests IS 'Pull Requests créées automatiquement';
COMMENT ON TABLE system_logs IS 'Logs système pour debugging et monitoring';
COMMENT ON TABLE webhook_events IS 'Événements webhook reçus de Monday.com';
COMMENT ON TABLE system_configurations IS 'Configurations système clé-valeur';