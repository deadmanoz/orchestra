import { useState } from 'react';
import { useCreateWorkflow } from '../hooks/useCreateWorkflow';
import type { WorkflowCreate } from '../types';

interface Props {
  onWorkflowCreated: (workflowId: string) => void;
}

export default function CreateWorkflowForm({ onWorkflowCreated }: Props) {
  const [name, setName] = useState('');
  const [type, setType] = useState<'plan_review' | 'implementation' | 'custom'>('plan_review');
  const [workspacePath, setWorkspacePath] = useState('');
  const [prompt, setPrompt] = useState('');

  const createWorkflow = useCreateWorkflow();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const data: WorkflowCreate = {
      name,
      type,
      initial_prompt: prompt,
      workspace_path: workspacePath,
    };

    try {
      const result = await createWorkflow.mutateAsync(data);
      onWorkflowCreated(result.id);
    } catch (error) {
      console.error('Failed to create workflow:', error);
    }
  };

  return (
    <div style={{
      maxWidth: '600px',
      margin: '0 auto',
      padding: '2rem',
      border: '1px solid #444',
      borderRadius: '8px',
      backgroundColor: '#1a1a1a'
    }}>
      <h2 style={{ marginTop: 0 }}>Create New Workflow</h2>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>
            Workflow Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My awesome project"
            required
            style={{
              width: '100%',
              padding: '0.5rem',
              fontSize: '1rem',
              borderRadius: '4px',
              border: '1px solid #444',
              backgroundColor: '#2a2a2a',
              color: 'white'
            }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>
            Workflow Type
          </label>
          <select
            value={type}
            onChange={(e) => setType(e.target.value as any)}
            style={{
              width: '100%',
              padding: '0.5rem',
              fontSize: '1rem',
              borderRadius: '4px',
              border: '1px solid #444',
              backgroundColor: '#2a2a2a',
              color: 'white'
            }}
          >
            <option value="plan_review">Plan & Review</option>
            <option value="implementation">Implementation</option>
            <option value="custom">Custom</option>
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>
            Workspace Path
          </label>
          <input
            type="text"
            value={workspacePath}
            onChange={(e) => setWorkspacePath(e.target.value)}
            placeholder="/path/to/your/codebase"
            required
            style={{
              width: '100%',
              padding: '0.5rem',
              fontSize: '1rem',
              borderRadius: '4px',
              border: '1px solid #444',
              backgroundColor: '#2a2a2a',
              color: 'white'
            }}
          />
          <small style={{ display: 'block', marginTop: '0.25rem', color: '#888', fontSize: '0.85rem' }}>
            Required: Absolute path to the directory where agents will work
          </small>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem' }}>
            Initial Prompt
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe what you want to build..."
            rows={6}
            required
            style={{
              width: '100%',
              padding: '0.5rem',
              fontSize: '1rem',
              borderRadius: '4px',
              border: '1px solid #444',
              backgroundColor: '#2a2a2a',
              color: 'white'
            }}
          />
        </div>

        <button
          type="submit"
          disabled={createWorkflow.isPending}
          style={{
            padding: '0.75rem',
            fontSize: '1rem',
            fontWeight: 'bold',
            backgroundColor: '#646cff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          {createWorkflow.isPending ? 'Creating...' : 'Start Workflow'}
        </button>

        {createWorkflow.isError && (
          <div style={{ color: '#ff6b6b', fontSize: '0.9rem' }}>
            Error: {createWorkflow.error.message}
          </div>
        )}
      </form>
    </div>
  );
}
