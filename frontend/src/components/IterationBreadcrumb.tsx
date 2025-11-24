import { useState, useEffect } from 'react';
import { CheckCircle2, Circle } from 'lucide-react';

interface HistoryStep {
  checkpoint_id: string;
  step_number: number;
  step_type: string;
  step_name: string;
  iteration_count: number;
  checkpoint_number: number;
  created_at: string | null;
}

interface IterationData {
  iteration: number;
  isActive: boolean;
  isCompleted: boolean;
}

interface Props {
  workflowId: string;
  currentIteration?: number;
}

// CSS animation for pulsing active iteration
const pulseAnimation = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  animation: 'pulse 2s ease-in-out infinite',
} as const;

// Inject keyframes into document (only once)
if (typeof document !== 'undefined' && !document.getElementById('pulse-keyframes')) {
  const style = document.createElement('style');
  style.id = 'pulse-keyframes';
  style.textContent = `
    @keyframes pulse {
      0%, 100% {
        opacity: 1;
      }
      50% {
        opacity: 0.5;
      }
    }
  `;
  document.head.appendChild(style);
}

export default function IterationBreadcrumb({ workflowId, currentIteration }: Props) {
  const [iterations, setIterations] = useState<IterationData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchIterations = async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/workflows/${workflowId}/history`);
        const data = await response.json();
        const history: HistoryStep[] = data.history || [];

        // Extract unique iterations and determine their status
        const iterationMap = new Map<number, { completed: boolean; lastCheckpointNumber: number }>();

        history.forEach(step => {
          const iter = step.iteration_count;
          const existing = iterationMap.get(iter);

          if (!existing || step.checkpoint_number > existing.lastCheckpointNumber) {
            // Check if this iteration is completed (has a subsequent iteration)
            const hasNextIteration = history.some(s => s.iteration_count > iter);
            iterationMap.set(iter, {
              completed: hasNextIteration,
              lastCheckpointNumber: step.checkpoint_number
            });
          }
        });

        // Convert to array and sort
        const iterationArray: IterationData[] = Array.from(iterationMap.entries())
          .map(([iteration, data]) => ({
            iteration,
            isCompleted: data.completed,
            isActive: iteration === (currentIteration ?? Math.max(...iterationMap.keys())),
          }))
          .sort((a, b) => a.iteration - b.iteration);

        setIterations(iterationArray);
      } catch (error) {
        console.error('Failed to fetch iteration history:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchIterations();

    // Poll for updates every 3 seconds
    const interval = setInterval(fetchIterations, 3000);
    return () => clearInterval(interval);
  }, [workflowId, currentIteration]);

  if (loading || iterations.length === 0) {
    return null;
  }

  // Show last 10 iterations, with overflow indicator
  const MAX_VISIBLE = 10;
  const hasOverflow = iterations.length > MAX_VISIBLE;
  const visibleIterations = hasOverflow
    ? iterations.slice(-MAX_VISIBLE)
    : iterations;

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '0.5rem',
      padding: '0.75rem 1rem',
      backgroundColor: '#0a0a0a',
      border: '1px solid #333',
      borderRadius: '6px',
      fontSize: '0.9rem',
      marginTop: '0.75rem',
    }}>
      <span style={{ color: '#888', fontWeight: 500, marginRight: '0.25rem' }}>
        Iterations:
      </span>

      {hasOverflow && (
        <span style={{ color: '#666', fontSize: '1.2rem', margin: '0 0.25rem' }}>
          •••
        </span>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        {visibleIterations.map((iter, index) => {
          const isLast = index === visibleIterations.length - 1;

          return (
            <div key={iter.iteration} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {/* Iteration Badge */}
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  padding: '0.35rem 0.6rem',
                  borderRadius: '4px',
                  backgroundColor: iter.isActive ? '#646cff' : (iter.isCompleted ? '#0a0a0a' : '#1a1a1a'),
                  border: iter.isActive ? '1px solid #646cff' : (iter.isCompleted ? '1px solid #333' : '1px solid #444'),
                  fontWeight: iter.isActive ? 600 : 500,
                  color: iter.isActive ? '#fff' : (iter.isCompleted ? '#51cf66' : '#888'),
                  transition: 'all 0.2s',
                }}
              >
                {/* Status Icon */}
                {iter.isCompleted ? (
                  <CheckCircle2 size={14} color="#51cf66" />
                ) : iter.isActive ? (
                  <span style={pulseAnimation}>
                    <Circle size={14} fill="#fff" color="#fff" />
                  </span>
                ) : (
                  <Circle size={14} color="#888" />
                )}

                {/* Iteration Number */}
                <span style={{ fontSize: '0.85rem' }}>
                  {iter.iteration}
                </span>
              </div>

              {/* Connector */}
              {!isLast && (
                <svg width="16" height="8" viewBox="0 0 16 8" style={{ flexShrink: 0 }}>
                  <line
                    x1="0"
                    y1="4"
                    x2="16"
                    y2="4"
                    stroke="#444"
                    strokeWidth="2"
                    strokeDasharray="2,2"
                  />
                </svg>
              )}
            </div>
          );
        })}
      </div>

      {/* Total Count (if overflowed) */}
      {hasOverflow && (
        <span style={{
          color: '#666',
          fontSize: '0.8rem',
          marginLeft: '0.5rem',
          fontStyle: 'italic'
        }}>
          (of {iterations.length})
        </span>
      )}
    </div>
  );
}
