import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Check, X, Edit3 } from 'lucide-react';
import type { Checkpoint } from '../types';
import { useResumeWorkflow } from '../hooks/useResumeWorkflow';

interface Props {
  workflowId: string;
  checkpoint: Checkpoint;
}

// Format action names for display (remove underscores, capitalize)
function formatActionName(action: string): string {
  return action
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

// Get content labels based on checkpoint step
function getContentLabels(stepName: string, isEditing: boolean): { title: string; editButton: string } {
  if (stepName === 'edit_reviewer_prompt') {
    return {
      title: isEditing ? '✏️ Editing Reviewer Prompt' : '📝 Reviewer Prompt',
      editButton: isEditing ? 'Preview' : 'Edit Reviewer Prompt'
    };
  } else if (stepName === 'edit_planner_prompt') {
    return {
      title: isEditing ? '✏️ Editing Planner Prompt' : '📝 Planner Prompt',
      editButton: isEditing ? 'Preview' : 'Edit Planner Prompt'
    };
  } else if (stepName === 'reviews_ready_for_consolidation') {
    return {
      title: isEditing ? '✏️ Editing Consolidated Feedback' : '📊 Consolidated Review Feedback',
      editButton: isEditing ? 'Preview' : 'Edit Consolidated Feedback'
    };
  } else {
    // Default for plan_ready_for_review
    return {
      title: isEditing ? '✏️ Editing Plan' : '📋 Current Plan',
      editButton: isEditing ? 'Preview' : 'Edit Plan'
    };
  }
}

export default function CheckpointEditor({ workflowId, checkpoint }: Props) {
  const [editedContent, setEditedContent] = useState(checkpoint.editable_content || '');
  const [userNotes, setUserNotes] = useState('');
  const [isEditing, setIsEditing] = useState(false);

  const resumeWorkflow = useResumeWorkflow(workflowId);
  const contentLabels = getContentLabels(checkpoint.step_name ?? '', isEditing);

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
      <div style={{ marginBottom: '1rem' }}>
        <h3 style={{ margin: '0 0 0.5rem 0' }}>
          🛑 Checkpoint #{checkpoint.checkpoint_number ?? 0}
        </h3>
        <p style={{ margin: 0, color: '#888', fontSize: '0.9rem' }}>
          {checkpoint.step_name ?? 'Unknown step'} • Iteration {checkpoint.iteration ?? 0}
        </p>
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

      {/* Agent Outputs - Only show reviewers, not the planner (plan is in editable content below) */}
      {checkpoint.agent_outputs && checkpoint.agent_outputs.length > 0 && (
        (() => {
          // Filter to only show review agents (role="review"), not the planner
          // This avoids duplication since the plan is shown in "Content to Review" section
          const reviewOutputs = checkpoint.agent_outputs.filter(
            output => output.agent_type === 'review' ||
                     output.agent_name?.includes('reviewer') ||
                     output.agent_name?.includes('review')
          );

          if (reviewOutputs.length === 0) {
            return null;
          }

          return (
            <div style={{ marginBottom: '1rem' }}>
              <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '1rem' }}>
                Reviews ({reviewOutputs.length})
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {reviewOutputs.map((output, idx) => (
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
                      marginBottom: '0.75rem',
                      fontSize: '0.9rem',
                      paddingBottom: '0.5rem',
                      borderBottom: '1px solid #222'
                    }}>
                      <span style={{ fontWeight: 600, color: '#51cf66' }}>
                        {output.agent_name}
                      </span>
                      {output.execution_time && (
                        <span style={{ color: '#888' }}>
                          {(output.execution_time / 1000).toFixed(1)}s
                        </span>
                      )}
                    </div>
                    <div style={{
                      fontSize: '0.95rem',
                      lineHeight: '1.6',
                      maxHeight: '400px',
                      overflow: 'auto'
                    }}>
                      <ReactMarkdown>{output.output}</ReactMarkdown>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })()
      )}

      {/* Editable Content - The plan/prompt that can be edited before approval */}
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
          <h4 style={{ margin: 0, fontSize: '1rem' }}>
            {contentLabels.title}
          </h4>
          <button
            onClick={() => setIsEditing(!isEditing)}
            style={{
              fontSize: '0.85rem',
              padding: '0.4rem 0.75rem',
              backgroundColor: isEditing ? '#646cff' : '#495057',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem'
            }}
          >
            <Edit3 size={14} />
            {contentLabels.editButton}
          </button>
        </div>
        {isEditing ? (
          <>
            <textarea
              value={editedContent}
              onChange={(e) => setEditedContent(e.target.value)}
              rows={15}
              style={{
                width: '100%',
                padding: '1rem',
                fontSize: '0.95rem',
                fontFamily: 'monospace',
                backgroundColor: '#0a0a0a',
                border: '2px solid #646cff',
                borderRadius: '4px',
                color: 'white',
                lineHeight: '1.5'
              }}
              placeholder="Edit the plan here..."
            />
            <div style={{
              fontSize: '0.85rem',
              color: '#888',
              marginTop: '0.5rem',
              fontStyle: 'italic'
            }}>
              💡 Tip: Edit the plan based on review feedback, then click approve to continue
            </div>
          </>
        ) : (
          <div style={{
            padding: '1rem',
            backgroundColor: '#0a0a0a',
            borderRadius: '4px',
            border: '1px solid #333',
            maxHeight: '400px',
            overflow: 'auto',
            lineHeight: '1.6'
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
          {formatActionName(checkpoint.actions?.primary || 'approve')}
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
            {action === 'cancel' && <X size={18} />}
            {formatActionName(action)}
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
