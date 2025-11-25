// Workflow types
export interface Workflow {
  id: string;
  name: string;
  type: string;
  status: string;
  workspace_path?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  metadata?: Record<string, any>;
  result?: Record<string, any>;
}

export interface WorkflowCreate {
  name: string;
  type: 'plan_review' | 'implementation' | 'custom';
  initial_prompt: string;
  workspace_path?: string;
  metadata?: Record<string, any>;
}

// Checkpoint types
export interface AgentOutput {
  agent_name: string;
  agent_type: string;
  output: string;
  timestamp: string;
  execution_time?: number;
}

export interface Checkpoint {
  checkpoint_id: string;
  checkpoint_number: number;
  step_name: string;
  workflow_id: string;
  iteration: number;
  agent_outputs: AgentOutput[];
  instructions: string;
  actions: {
    primary: string;
    secondary: string[];
  };
  editable_content: string;
  context?: Record<string, any>;
}

export interface CheckpointResolution {
  action: string;
  edited_content?: string;
  user_notes?: string;
}

// Workflow state snapshot
export interface WorkflowStateSnapshot {
  workflow: Workflow;
  pending_checkpoint: Checkpoint | null;
  recent_messages: Message[];
  agent_executions: AgentExecution[];
  current_iteration: number;  // Current iteration from workflow state
}

export interface Message {
  id: number;
  workflow_id: string;
  role: string;
  content: string;
  agent_name?: string;
  created_at: string;
}

export interface AgentExecution {
  id: number;
  workflow_id: string;
  agent_name: string;
  agent_type: string;
  input_content: string;
  output_content?: string;
  status: string;
  started_at: string;
  completed_at?: string;
  execution_time_ms?: number;
}

// WebSocket message types
export interface WebSocketMessage {
  type: 'status_update' | 'checkpoint_ready' | 'error';
  workflow_id: string;
  status?: string;
  timestamp: string;
  data?: any;
}
