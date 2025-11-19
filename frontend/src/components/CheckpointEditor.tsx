import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Check, X, Edit3 } from 'lucide-react';
import type { Checkpoint } from '../types';
import { useResumeWorkflow } from '../hooks/useResumeWorkflow';

interface Props {
  workflowId: string;
  checkpoint: Checkpoint;
}

export default function CheckpointEditor({ workflowId, checkpoint }: Props) {
  const [editedContent, setEditedContent] = useState(checkpoint.editable_content || '');
  const [userNotes, setUserNotes] = useState('');
  const [isEditing, setIsEditing] = useState(false);

  const resumeWorkflow = useResumeWorkflow(workflowId);

  // Safety check
  if (!checkpoint) {
    return <div style={{ color: '#ff6b6b' }}>Error: No checkpoint data available</div>;
  }

  const handleAction = async (action: string) => {
    try {
      await resumeWorkflow.mutateAsync({
        action,
        edited_content: editedContent,
        user_notes: userNotes || undefined,
      });
      // Reset form
      setUserNotes('');
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to resume workflow:', error);
    }
  };

  return (
    <div style={{
      position: 'sticky',
      bottom: 0,
      padding: '1.5rem',
      border: '2px solid #646cff',
      borderRadius: '8px',
      backgroundColor: '#1a1a1a',
      boxShadow: '0 -4px 12px rgba(0,0,0,0.3)'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '1rem' }}>
        <div>
          <h3 style={{ margin: '0 0 0.5rem 0' }}>
            🛑 Checkpoint #{checkpoint.checkpoint_number ?? 0}
          </h3>
          <p style={{ margin: 0, color: '#888', fontSize: '0.9rem' }}>
            {checkpoint.step_name ?? 'Unknown step'} • Iteration {checkpoint.iteration ?? 0}
          </p>
        </div>
        <button
          onClick={() => setIsEditing(!isEditing)}
          style={{
            fontSize: '0.9rem',
            backgroundColor: isEditing ? '#646cff' : 'transparent'
          }}
        >
          <Edit3 size={16} style={{ marginRight: '0.5rem', verticalAlign: 'middle' }} />
          {isEditing ? 'Preview' : 'Edit'}
        </button>
      </div>

      {/* Instructions */}
      {checkpoint.instructions && (
        <div style={{
          padding: '1rem',
          backgroundColor: '#2a2a2a',
          borderRadius: '4px',
          marginBottom: '1rem',
          fontSize: '0.95rem'
        }}>
          <strong>Instructions:</strong> {checkpoint.instructions}
        </div>
      )}

      {/* Agent Outputs */}
      {checkpoint.agent_outputs && checkpoint.agent_outputs.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '1rem' }}>Agent Outputs</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {checkpoint.agent_outputs.map((output, idx) => (
              <div
                key={idx}
                style={{
                  padding: '1rem',
                  backgroundColor: '#0a0a0a',
                  borderRadius: '4px',
                  border: '1px solid #333'
                }}
              >
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginBottom: '0.5rem',
                  fontSize: '0.9rem',
                  color: '#888'
                }}>
                  <span><strong>{output.agent_name}</strong> ({output.agent_type})</span>
                  {output.execution_time && (
                    <span>{(output.execution_time / 1000).toFixed(1)}s</span>
                  )}
                </div>
                <div style={{ fontSize: '0.95rem', whiteSpace: 'pre-wrap' }}>
                  {output.output}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Editable Content */}
      <div style={{ marginBottom: '1rem' }}>
        <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '1rem' }}>Content to Review</h4>
        {isEditing ? (
          <textarea
            value={editedContent}
            onChange={(e) => setEditedContent(e.target.value)}
            rows={12}
            style={{
              width: '100%',
              padding: '1rem',
              fontSize: '0.95rem',
              fontFamily: 'monospace',
              backgroundColor: '#0a0a0a',
              border: '1px solid #444',
              borderRadius: '4px',
              color: 'white'
            }}
          />
        ) : (
          <div style={{
            padding: '1rem',
            backgroundColor: '#0a0a0a',
            borderRadius: '4px',
            border: '1px solid #333',
            maxHeight: '300px',
            overflow: 'auto'
          }}>
            <ReactMarkdown>{editedContent}</ReactMarkdown>
          </div>
        )}
      </div>

      {/* User Notes */}
      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.95rem' }}>
          Optional Notes for Agents
        </label>
        <textarea
          value={userNotes}
          onChange={(e) => setUserNotes(e.target.value)}
          placeholder="Add any comments or guidance for the next iteration..."
          rows={3}
          style={{
            width: '100%',
            padding: '0.75rem',
            fontSize: '0.9rem',
            backgroundColor: '#2a2a2a',
            border: '1px solid #444',
            borderRadius: '4px',
            color: 'white'
          }}
        />
      </div>

      {/* Action Buttons */}
      <div style={{ display: 'flex', gap: '1rem' }}>
        <button
          onClick={() => handleAction(checkpoint.actions?.primary || 'approve')}
          disabled={resumeWorkflow.isPending}
          style={{
            flex: 2,
            padding: '0.75rem',
            fontSize: '1rem',
            fontWeight: 'bold',
            backgroundColor: '#51cf66',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem'
          }}
        >
          <Check size={20} />
          {checkpoint.actions?.primary || 'Approve'}
        </button>

        {checkpoint.actions?.secondary && checkpoint.actions.secondary.map((action) => (
          <button
            key={action}
            onClick={() => handleAction(action)}
            disabled={resumeWorkflow.isPending}
            style={{
              flex: 1,
              padding: '0.75rem',
              fontSize: '0.95rem',
              backgroundColor: '#495057',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem'
            }}
          >
            {action === 'reject' && <X size={18} />}
            {action}
          </button>
        ))}
      </div>

      {resumeWorkflow.isError && (
        <div style={{ marginTop: '1rem', color: '#ff6b6b', fontSize: '0.9rem' }}>
          Error: {resumeWorkflow.error.message}
        </div>
      )}

      {resumeWorkflow.isPending && (
        <div style={{ marginTop: '1rem', color: '#ffd43b', fontSize: '0.9rem' }}>
          Processing...
        </div>
      )}
    </div>
  );
}
