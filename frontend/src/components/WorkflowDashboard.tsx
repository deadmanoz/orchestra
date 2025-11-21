import { useState, useEffect } from 'react';
import type { Workflow, Message, AgentExecution, Checkpoint } from '../types';
import { CheckCircle, Clock, XCircle, PlayCircle, Folder, Loader2 } from 'lucide-react';

interface Props {
  workflow: Workflow;
  messages: Message[];
  executions: AgentExecution[];
  pendingCheckpoint: Checkpoint | null;
  onReset: () => void;
}

// CSS animation for spinning loader
const spinAnimation = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  animation: 'spin 1s linear infinite',
} as const;

// Inject keyframes into document (only once)
if (typeof document !== 'undefined' && !document.getElementById('loader-spin-keyframes')) {
  const style = document.createElement('style');
  style.id = 'loader-spin-keyframes';
  style.textContent = `
    @keyframes spin {
      from {
        transform: rotate(0deg);
      }
      to {
        transform: rotate(360deg);
      }
    }
  `;
  document.head.appendChild(style);
}

// Get descriptive status message based on workflow state
function getWorkflowStatusMessage(
  workflow: Workflow,
  pendingCheckpoint: Checkpoint | null,
  executions: AgentExecution[]
): { message: string; showSpinner: boolean } {
  // Check if any agents are currently running
  const runningAgents = executions.filter(e => e.status === 'running');

  if (workflow.status === 'completed') {
    return { message: 'Workflow completed successfully', showSpinner: false };
  }

  if (workflow.status === 'failed') {
    return { message: 'Workflow failed', showSpinner: false };
  }

  // Determine current stage based on checkpoint and running agents
  if (runningAgents.length > 0) {
    const agentTypes = runningAgents.map(a => a.agent_type);

    if (agentTypes.includes('planning')) {
      const iteration = pendingCheckpoint?.iteration ?? 0;
      if (iteration === 0) {
        return { message: 'Planning agent crafting initial plan...', showSpinner: true };
      } else {
        return { message: `Planning agent revising plan (iteration ${iteration + 1})...`, showSpinner: true };
      }
    }

    if (agentTypes.includes('review')) {
      const iteration = pendingCheckpoint?.iteration ?? 0;
      const planVersion = iteration + 1;
      return { message: `Review agents reviewing plan (v${planVersion})...`, showSpinner: true };
    }

    return { message: 'Agents working...', showSpinner: true };
  }

  // If paused/awaiting checkpoint
  if (workflow.status === 'paused' && pendingCheckpoint) {
    const stepName = pendingCheckpoint.step_name;

    if (stepName === 'plan_ready_for_review') {
      return { message: 'Plan ready for your review', showSpinner: false };
    }

    if (stepName === 'reviews_ready_for_consolidation') {
      return { message: 'Reviews ready for your decision', showSpinner: false };
    }

    if (stepName === 'edit_reviewer_prompt') {
      return { message: 'Edit reviewer prompt', showSpinner: false };
    }

    if (stepName === 'edit_planner_prompt') {
      return { message: 'Edit planner prompt', showSpinner: false };
    }

    return { message: 'Awaiting your input', showSpinner: false };
  }

  if (workflow.status === 'running') {
    return { message: 'Workflow in progress...', showSpinner: true };
  }

  return { message: workflow.status, showSpinner: false };
}

// Timer component to show elapsed time
function ElapsedTimer({ startTime }: { startTime: string }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = new Date(startTime).getTime();

    const updateElapsed = () => {
      const now = Date.now();
      setElapsed(now - start);
    };

    updateElapsed(); // Initial update
    const interval = setInterval(updateElapsed, 100); // Update every 100ms

    return () => clearInterval(interval);
  }, [startTime]);

  const formatElapsed = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;

    if (minutes > 0) {
      return `${minutes}m ${remainingSeconds}s`;
    }
    return `${seconds}s`;
  };

  return <span>{formatElapsed(elapsed)}</span>;
}

export default function WorkflowDashboard({ workflow, messages, executions, pendingCheckpoint, onReset }: Props) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle color="#51cf66" size={20} />;
      case 'running':
        return (
          <span style={spinAnimation}>
            <Loader2 color="#ffd43b" size={20} />
          </span>
        );
      case 'paused':
        return <Clock color="#ffd43b" size={20} />;
      case 'failed':
        return <XCircle color="#ff6b6b" size={20} />;
      default:
        return <PlayCircle color="#888" size={20} />;
    }
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return 'N/A';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  // Get descriptive status message
  const statusInfo = getWorkflowStatusMessage(workflow, pendingCheckpoint, executions);

  // Find the most recent running agent to show timer for
  const runningAgents = executions.filter(e => e.status === 'running');
  const latestRunningAgent = runningAgents.length > 0 ? runningAgents[runningAgents.length - 1] : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Workflow Header */}
      <div style={{
        padding: '1.5rem',
        border: '1px solid #444',
        borderRadius: '8px',
        backgroundColor: '#1a1a1a'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
          <div style={{ flex: 1 }}>
            <h2 style={{ margin: '0 0 0.5rem 0' }}>{workflow.name}</h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#888', marginBottom: '0.5rem' }}>
              {statusInfo.showSpinner ? (
                <span style={spinAnimation}>
                  <Loader2 color="#ffd43b" size={20} />
                </span>
              ) : (
                getStatusIcon(workflow.status)
              )}
              <span>{statusInfo.message}</span>
              {latestRunningAgent && (
                <>
                  <span>•</span>
                  <ElapsedTimer startTime={latestRunningAgent.started_at} />
                </>
              )}
            </div>
            {workflow.workspace_path && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#888', fontSize: '0.9rem' }}>
                <Folder size={16} />
                <code style={{ backgroundColor: '#0a0a0a', padding: '0.25rem 0.5rem', borderRadius: '3px' }}>
                  {workflow.workspace_path}
                </code>
              </div>
            )}
          </div>
          <button onClick={onReset} style={{ fontSize: '0.9rem' }}>
            New Workflow
          </button>
        </div>
      </div>

      {/* Agent Executions */}
      {executions.length > 0 && (
        <div style={{
          padding: '1.5rem',
          border: '1px solid #444',
          borderRadius: '8px',
          backgroundColor: '#1a1a1a'
        }}>
          <h3 style={{ marginTop: 0 }}>Agent Executions</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {executions.map((execution) => (
              <div
                key={execution.id}
                style={{
                  padding: '1rem',
                  border: '1px solid #333',
                  borderRadius: '4px',
                  backgroundColor: '#0a0a0a'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <div>
                    <strong>{execution.agent_name}</strong>
                    <span style={{ color: '#888', marginLeft: '0.5rem' }}>
                      ({execution.agent_type})
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {getStatusIcon(execution.status)}
                    <span style={{ fontSize: '0.9rem', color: execution.status === 'completed' ? '#51cf66' : '#888', fontWeight: execution.status === 'completed' ? 'bold' : 'normal' }}>
                      {execution.status === 'running' ? (
                        <ElapsedTimer startTime={execution.started_at} />
                      ) : (
                        formatDuration(execution.execution_time_ms)
                      )}
                    </span>
                  </div>
                </div>
                {execution.output_content && (
                  <div style={{
                    fontSize: '0.9rem',
                    color: '#ccc',
                    whiteSpace: 'pre-wrap',
                    maxHeight: '200px',
                    overflow: 'auto'
                  }}>
                    {execution.output_content}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Messages */}
      {messages.length > 0 && (
        <div style={{
          padding: '1.5rem',
          border: '1px solid #444',
          borderRadius: '8px',
          backgroundColor: '#1a1a1a'
        }}>
          <h3 style={{ marginTop: 0 }}>Recent Messages</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {messages.map((message) => (
              <div
                key={message.id}
                style={{
                  padding: '0.75rem',
                  borderLeft: message.role === 'user' ? '3px solid #646cff' : '3px solid #51cf66',
                  backgroundColor: '#0a0a0a',
                  borderRadius: '4px'
                }}
              >
                <div style={{ fontSize: '0.85rem', color: '#888', marginBottom: '0.25rem' }}>
                  {message.role === 'user' ? '👤 User' : `🤖 ${message.agent_name || 'Agent'}`}
                </div>
                <div style={{ fontSize: '0.95rem', whiteSpace: 'pre-wrap' }}>
                  {message.content}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
