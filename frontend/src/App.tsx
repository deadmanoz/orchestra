import { useState, useEffect } from 'react';
import WorkflowDashboard from './components/WorkflowDashboard';
import WorkflowTimeline from './components/WorkflowTimeline';
import CreateWorkflowForm from './components/CreateWorkflowForm';
import CheckpointEditor from './components/CheckpointEditor';
import ErrorBoundary from './components/ErrorBoundary';
import { useWorkflow } from './hooks/useWorkflow';
import { useWebSocket } from './hooks/useWebSocket';

// Get workflow ID from URL hash (e.g., #workflow/wf-abc123)
function getWorkflowIdFromUrl(): string | null {
  const hash = window.location.hash;
  if (hash.startsWith('#workflow/')) {
    return hash.slice('#workflow/'.length);
  }
  return null;
}

// Update URL hash with workflow ID
function setWorkflowIdInUrl(workflowId: string | null) {
  if (workflowId) {
    window.location.hash = `workflow/${workflowId}`;
  } else {
    // Clear hash without triggering hashchange
    history.replaceState(null, '', window.location.pathname + window.location.search);
  }
}

function App() {
  // Initialize from URL hash
  const [currentWorkflowId, setCurrentWorkflowId] = useState<string | null>(getWorkflowIdFromUrl);
  const { data: workflowData, isLoading, error } = useWorkflow(currentWorkflowId);

  // Enable WebSocket for real-time updates
  useWebSocket(currentWorkflowId);

  // Sync URL hash with workflow ID
  useEffect(() => {
    setWorkflowIdInUrl(currentWorkflowId);
  }, [currentWorkflowId]);

  // Listen for hash changes (browser back/forward)
  useEffect(() => {
    const handleHashChange = () => {
      const id = getWorkflowIdFromUrl();
      setCurrentWorkflowId(id);
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      padding: '2rem',
      gap: '2rem'
    }}>
      <header>
        <h1 style={{ margin: 0, marginBottom: '0.5rem' }}>🎭 Orchestra</h1>
        <p style={{ margin: 0, color: '#888' }}>
          Multi-agent orchestration with human-in-the-loop checkpoints
        </p>
      </header>

      {!currentWorkflowId ? (
        <CreateWorkflowForm onWorkflowCreated={setCurrentWorkflowId} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', flex: 1 }}>
          {isLoading && <div>Loading workflow...</div>}
          {error && <div style={{ color: '#ff6b6b' }}>Error: {error.message}</div>}

          {workflowData && (
            <ErrorBoundary>
              <WorkflowDashboard
                workflow={workflowData.workflow}
                messages={workflowData.recent_messages}
                executions={workflowData.agent_executions}
                pendingCheckpoint={workflowData.pending_checkpoint}
                currentIteration={workflowData.current_iteration ?? 0}
                onReset={() => setCurrentWorkflowId(null)}
              />

              {/* Workflow History Timeline */}
              <ErrorBoundary>
                <WorkflowTimeline workflowId={currentWorkflowId} />
              </ErrorBoundary>

              {workflowData.pending_checkpoint && (
                <ErrorBoundary>
                  <CheckpointEditor
                    workflowId={currentWorkflowId}
                    checkpoint={workflowData.pending_checkpoint}
                  />
                </ErrorBoundary>
              )}
            </ErrorBoundary>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
