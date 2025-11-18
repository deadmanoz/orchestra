import type { Workflow, Message, AgentExecution } from '../types';
import { CheckCircle, Clock, XCircle, PlayCircle } from 'lucide-react';

interface Props {
  workflow: Workflow;
  messages: Message[];
  executions: AgentExecution[];
  onReset: () => void;
}

export default function WorkflowDashboard({ workflow, messages, executions, onReset }: Props) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle color="#51cf66" size={20} />;
      case 'running':
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
          <div>
            <h2 style={{ margin: '0 0 0.5rem 0' }}>{workflow.name}</h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#888' }}>
              {getStatusIcon(workflow.status)}
              <span style={{ textTransform: 'capitalize' }}>{workflow.status}</span>
              <span>•</span>
              <span>{workflow.type}</span>
            </div>
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
                    <span style={{ fontSize: '0.9rem', color: '#888' }}>
                      {formatDuration(execution.execution_time_ms)}
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
