import { useState, useEffect } from 'react';
import type { Workflow, Message, AgentExecution, Checkpoint } from '../types';
import { CheckCircle, Clock, XCircle, PlayCircle, Folder, Loader2, ChevronDown, ChevronRight } from 'lucide-react';
import { WorkflowStatus, CheckpointStep } from '../constants/workflowStatus';
import IterationBreadcrumb from './IterationBreadcrumb';

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

// Format duration for display
function formatDuration(ms?: number): string {
  if (!ms) return 'N/A';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// Get descriptive status message based on workflow state
function getWorkflowStatusMessage(
  workflow: Workflow,
  pendingCheckpoint: Checkpoint | null,
  executions: AgentExecution[]
): { message: string; showSpinner: boolean } {
  if (workflow.status === WorkflowStatus.COMPLETED) {
    return { message: 'Workflow completed successfully', showSpinner: false };
  }

  if (workflow.status === WorkflowStatus.FAILED) {
    return { message: 'Workflow failed', showSpinner: false };
  }

  // If awaiting checkpoint
  if (workflow.status === WorkflowStatus.AWAITING_CHECKPOINT && pendingCheckpoint) {
    const stepName = pendingCheckpoint.step_name;

    if (stepName === CheckpointStep.PLAN_READY_FOR_REVIEW) {
      return { message: 'Plan ready for your review', showSpinner: false };
    }

    if (stepName === CheckpointStep.REVIEWS_READY_FOR_CONSOLIDATION) {
      return { message: 'Reviews ready for your decision', showSpinner: false };
    }

    if (stepName === CheckpointStep.EDIT_REVIEWER_PROMPT) {
      return { message: 'Edit reviewer prompt', showSpinner: false };
    }

    if (stepName === CheckpointStep.EDIT_PLANNER_PROMPT) {
      return { message: 'Edit planner prompt', showSpinner: false };
    }

    return { message: 'Awaiting your input', showSpinner: false };
  }

  // Workflow is running - determine what's happening
  if (workflow.status === WorkflowStatus.RUNNING) {
    // Check if any agents are currently running
    const runningAgents = executions.filter(e => e.status === WorkflowStatus.RUNNING);
    const agentTypes = runningAgents.map(a => a.agent_type);

    // If we have running agents, show status based on agent type
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

      // Get all review agent executions (running or completed in this batch)
      const reviewAgents = executions.filter(e => e.agent_type === 'review');

      // Sort by ID to maintain consistent order (REVIEW AGENT 1, 2, 3)
      const sortedReviewAgents = reviewAgents.sort((a, b) => a.id - b.id);

      // Get the most recent batch of review agents (those from current iteration)
      const latestReviewBatch = sortedReviewAgents.slice(-3); // Assume 3 review agents max

      // Build individual status strings
      const agentStatuses = latestReviewBatch.map((agent, idx) => {
        const agentNum = idx + 1;
        if (agent.status === 'completed') {
          return `Agent ${agentNum} ✓ (${formatDuration(agent.execution_time_ms)})`;
        } else if (agent.status === 'running') {
          return `Agent ${agentNum} running...`;
        } else if (agent.status === 'failed') {
          return `Agent ${agentNum} ✗`;
        } else {
          return `Agent ${agentNum} pending`;
        }
      });

      const statusText = agentStatuses.join(' | ');
      return { message: `Review agents (v${planVersion}): ${statusText}`, showSpinner: true };
    }

    if (runningAgents.length > 0) {
      return { message: 'Agents working...', showSpinner: true };
    }

    // No running agents yet - infer from workflow state
    // Check if we have any executions at all
    if (executions.length === 0) {
      // Just started - must be planning agent starting
      return { message: 'Planning agent crafting initial plan...', showSpinner: true };
    }

    // Check the most recent execution to infer what should happen next
    const sortedExecutions = [...executions].sort((a, b) =>
      new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
    );
    const lastExecution = sortedExecutions[0];

    // If last execution was planning, reviewers should be next
    if (lastExecution.agent_type === 'planning' && lastExecution.status === 'completed') {
      const iteration = pendingCheckpoint?.iteration ?? 0;
      const planVersion = iteration + 1;

      // Check if there are any review agents that have started
      const reviewAgents = executions.filter(e => e.agent_type === 'review');
      if (reviewAgents.length > 0) {
        // Sort by ID to maintain consistent order
        const sortedReviewAgents = reviewAgents.sort((a, b) => a.id - b.id);
        const latestReviewBatch = sortedReviewAgents.slice(-3);

        const agentStatuses = latestReviewBatch.map((agent, idx) => {
          const agentNum = idx + 1;
          if (agent.status === 'completed') {
            return `Agent ${agentNum} ✓ (${formatDuration(agent.execution_time_ms)})`;
          } else if (agent.status === 'running') {
            return `Agent ${agentNum} running...`;
          } else if (agent.status === 'failed') {
            return `Agent ${agentNum} ✗`;
          } else {
            return `Agent ${agentNum} pending`;
          }
        });

        const statusText = agentStatuses.join(' | ');
        return { message: `Review agents (v${planVersion}): ${statusText}`, showSpinner: true };
      }

      // Fallback if no review agents have started yet
      return { message: `Review agents starting (v${planVersion})...`, showSpinner: true };
    }

    // If last executions were reviews, planning agent should be next (revision)
    const recentReviews = sortedExecutions.filter(e => e.agent_type === 'review' && e.status === 'completed');
    if (recentReviews.length > 0) {
      const iteration = (pendingCheckpoint?.iteration ?? 0) + 1;
      return { message: `Planning agent revising plan (iteration ${iteration + 1})...`, showSpinner: true };
    }

    // Default fallback
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

// Component for individual agent execution with collapsible content
function AgentExecutionItem({ execution }: { execution: AgentExecution }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case WorkflowStatus.COMPLETED:
        return <CheckCircle color="#51cf66" size={20} />;
      case WorkflowStatus.RUNNING:
        return (
          <span style={spinAnimation}>
            <Loader2 color="#ffd43b" size={20} />
          </span>
        );
      case WorkflowStatus.AWAITING_CHECKPOINT:
        return <Clock color="#ffd43b" size={20} />;
      case WorkflowStatus.FAILED:
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

  return (
    <div
      style={{
        padding: '1rem',
        border: '1px solid #333',
        borderRadius: '4px',
        backgroundColor: '#0a0a0a'
      }}
    >
      <div
        onClick={() => execution.output_content && setIsExpanded(!isExpanded)}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          cursor: execution.output_content ? 'pointer' : 'default',
          userSelect: 'none'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1 }}>
          {execution.output_content && (
            isExpanded ? <ChevronDown size={16} color="#888" /> : <ChevronRight size={16} color="#888" />
          )}
          <strong>{execution.agent_name}</strong>
          <span style={{ color: '#888' }}>
            ({execution.agent_type})
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {getStatusIcon(execution.status)}
          <span style={{ fontSize: '0.9rem', color: execution.status === WorkflowStatus.COMPLETED ? '#51cf66' : '#888', fontWeight: execution.status === WorkflowStatus.COMPLETED ? 'bold' : 'normal' }}>
            {execution.status === WorkflowStatus.RUNNING ? (
              <ElapsedTimer startTime={execution.started_at} />
            ) : (
              formatDuration(execution.execution_time_ms)
            )}
          </span>
        </div>
      </div>
      {isExpanded && execution.output_content && (
        <div style={{
          marginTop: '1rem',
          paddingTop: '1rem',
          borderTop: '1px solid #333',
          fontSize: '0.9rem',
          color: '#ccc',
          whiteSpace: 'pre-wrap',
          maxHeight: '400px',
          overflow: 'auto'
        }}>
          {execution.output_content}
        </div>
      )}
    </div>
  );
}

export default function WorkflowDashboard({ workflow, messages, executions, pendingCheckpoint, onReset }: Props) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case WorkflowStatus.COMPLETED:
        return <CheckCircle color="#51cf66" size={20} />;
      case WorkflowStatus.RUNNING:
        return (
          <span style={spinAnimation}>
            <Loader2 color="#ffd43b" size={20} />
          </span>
        );
      case WorkflowStatus.AWAITING_CHECKPOINT:
        return <Clock color="#ffd43b" size={20} />;
      case WorkflowStatus.FAILED:
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

  // Determine what timestamp to use for the timer
  const getTimerStartTime = (): string | null => {
    // If there's a running agent, use its start time
    if (latestRunningAgent) {
      return latestRunningAgent.started_at;
    }

    // If workflow is running but no running agents yet, use workflow's updated_at
    if (workflow.status === WorkflowStatus.RUNNING) {
      return workflow.updated_at;
    }

    return null;
  };

  const timerStartTime = getTimerStartTime();

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
              {timerStartTime && (
                <>
                  <span>•</span>
                  <ElapsedTimer startTime={timerStartTime} />
                </>
              )}
            </div>

            {/* Iteration Breadcrumb Trail */}
            <IterationBreadcrumb
              workflowId={workflow.id}
              currentIteration={pendingCheckpoint?.iteration}
            />

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
              <AgentExecutionItem key={execution.id} execution={execution} />
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
