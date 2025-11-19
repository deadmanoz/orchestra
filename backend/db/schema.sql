-- Workflows table
CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'awaiting_checkpoint', 'completed', 'failed', 'cancelled')),
    workspace_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    created_by TEXT,
    metadata JSON,
    result JSON
);

-- Checkpoints table (supplements LangGraph checkpoints)
CREATE TABLE IF NOT EXISTS user_checkpoints (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    checkpoint_number INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    agent_outputs JSON NOT NULL,
    user_edited_content TEXT,
    user_notes TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected', 'edited')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_by TEXT,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

-- Agent executions table
CREATE TABLE IF NOT EXISTS agent_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    agent_type TEXT NOT NULL,
    input_content TEXT NOT NULL,
    output_content TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed')),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    execution_time_ms INTEGER,
    cost_usd DECIMAL(10, 6),
    metadata JSON,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

-- Agent sessions table (for subprocess agents)
CREATE TABLE IF NOT EXISTS agent_sessions (
    id TEXT PRIMARY KEY,
    agent_type TEXT NOT NULL,
    port INTEGER NOT NULL,
    pid INTEGER,
    status TEXT NOT NULL CHECK(status IN ('starting', 'running', 'stopped', 'error')),
    working_directory TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    stopped_at TIMESTAMP,
    metadata JSON
);

-- Messages table (full conversation log)
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'ai', 'system')),
    content TEXT NOT NULL,
    agent_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status);
CREATE INDEX IF NOT EXISTS idx_workflows_created_at ON workflows(created_at);
CREATE INDEX IF NOT EXISTS idx_checkpoints_workflow ON user_checkpoints(workflow_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_status ON user_checkpoints(status);
CREATE INDEX IF NOT EXISTS idx_executions_workflow ON agent_executions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_messages_workflow ON messages(workflow_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON agent_sessions(status);
