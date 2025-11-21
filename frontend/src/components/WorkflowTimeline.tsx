import { useState, useEffect } from 'react';
import { ChevronRight, ChevronDown, FileText, MessageSquare, CheckCircle2 } from 'lucide-react';

interface HistoryStep {
  checkpoint_id: string;
  step_number: number;
  step_type: string;
  step_name: string;
  iteration_count: number;
  checkpoint_number: number;
  created_at: string | null;
  current_plan: string;
  reviews: Array<{
    agent_name: string;
    agent_type: string;
    feedback: string;
  }>;
  instructions: string;
  actions: string[];
}

interface Props {
  workflowId: string;
}

export default function WorkflowTimeline({ workflowId }: Props) {
  const [history, setHistory] = useState<HistoryStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedStep, setExpandedStep] = useState<number | null>(null);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/workflows/${workflowId}/history`);
        const data = await response.json();
        setHistory(data.history || []);
      } catch (error) {
        console.error('Failed to fetch workflow history:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();

    // Poll for updates every 5 seconds
    const interval = setInterval(fetchHistory, 5000);
    return () => clearInterval(interval);
  }, [workflowId]);

  const getStepIcon = (stepType: string) => {
    switch (stepType) {
      case 'plan':
        return <FileText size={18} color="#646cff" />;
      case 'review':
        return <MessageSquare size={18} color="#51cf66" />;
      default:
        return <CheckCircle2 size={18} color="#888" />;
    }
  };

  const formatTimestamp = (timestamp: string | null) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  if (loading) {
    return (
      <div style={{
        padding: '1.5rem',
        border: '1px solid #444',
        borderRadius: '8px',
        backgroundColor: '#1a1a1a'
      }}>
        <h3 style={{ marginTop: 0 }}>Workflow History</h3>
        <p style={{ color: '#888' }}>Loading timeline...</p>
      </div>
    );
  }

  if (history.length === 0) {
    return null;
  }

  return (
    <div style={{
      padding: '1.5rem',
      border: '1px solid #444',
      borderRadius: '8px',
      backgroundColor: '#1a1a1a'
    }}>
      <h3 style={{ marginTop: 0, marginBottom: '1rem' }}>
        Workflow Progress ({history.length} {history.length === 1 ? 'step' : 'steps'})
      </h3>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {history.map((step, index) => {
          const isExpanded = expandedStep === index;
          const isLastStep = index === history.length - 1;

          return (
            <div key={step.checkpoint_id}>
              {/* Timeline Step */}
              <div
                onClick={() => setExpandedStep(isExpanded ? null : index)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                  padding: '0.75rem',
                  backgroundColor: isLastStep ? '#2a2a2a' : '#0a0a0a',
                  border: isLastStep ? '1px solid #646cff' : '1px solid #333',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = isLastStep ? '#353535' : '#1a1a1a';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = isLastStep ? '#2a2a2a' : '#0a0a0a';
                }}
              >
                {/* Expand/Collapse Icon */}
                <div style={{ flexShrink: 0 }}>
                  {isExpanded ? (
                    <ChevronDown size={16} color="#888" />
                  ) : (
                    <ChevronRight size={16} color="#888" />
                  )}
                </div>

                {/* Step Icon */}
                <div style={{ flexShrink: 0 }}>
                  {getStepIcon(step.step_type)}
                </div>

                {/* Step Info */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 500, fontSize: '0.95rem' }}>
                    {step.step_name}
                  </div>
                  {step.created_at && (
                    <div style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.125rem' }}>
                      {formatTimestamp(step.created_at)}
                    </div>
                  )}
                </div>

                {/* Current Step Indicator */}
                {isLastStep && (
                  <div style={{
                    fontSize: '0.75rem',
                    padding: '0.25rem 0.5rem',
                    backgroundColor: '#646cff',
                    borderRadius: '3px',
                    fontWeight: 500
                  }}>
                    Current
                  </div>
                )}
              </div>

              {/* Expanded Content */}
              {isExpanded && (
                <div style={{
                  marginTop: '0.5rem',
                  marginLeft: '2.5rem',
                  padding: '1rem',
                  backgroundColor: '#0a0a0a',
                  border: '1px solid #333',
                  borderRadius: '4px'
                }}>
                  {/* Plan Content */}
                  {step.current_plan && (
                    <div style={{ marginBottom: '1rem' }}>
                      <div style={{
                        fontSize: '0.85rem',
                        fontWeight: 600,
                        color: '#888',
                        marginBottom: '0.5rem',
                        textTransform: 'uppercase'
                      }}>
                        Plan
                      </div>
                      <div style={{
                        fontSize: '0.9rem',
                        whiteSpace: 'pre-wrap',
                        backgroundColor: '#000',
                        padding: '0.75rem',
                        borderRadius: '4px',
                        maxHeight: '400px',
                        overflow: 'auto',
                        fontFamily: 'monospace',
                        lineHeight: '1.5'
                      }}>
                        {step.current_plan}
                      </div>
                    </div>
                  )}

                  {/* Reviews */}
                  {step.reviews && step.reviews.length > 0 && (
                    <div>
                      <div style={{
                        fontSize: '0.85rem',
                        fontWeight: 600,
                        color: '#888',
                        marginBottom: '0.5rem',
                        textTransform: 'uppercase'
                      }}>
                        Reviews ({step.reviews.length})
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        {step.reviews.map((review, idx) => (
                          <div
                            key={idx}
                            style={{
                              padding: '0.75rem',
                              backgroundColor: '#000',
                              border: '1px solid #222',
                              borderRadius: '4px'
                            }}
                          >
                            <div style={{
                              fontSize: '0.85rem',
                              fontWeight: 600,
                              marginBottom: '0.5rem',
                              color: '#51cf66'
                            }}>
                              {review.agent_name} ({review.agent_type})
                            </div>
                            <div style={{
                              fontSize: '0.9rem',
                              whiteSpace: 'pre-wrap',
                              lineHeight: '1.5'
                            }}>
                              {review.feedback}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Instructions */}
                  {step.instructions && (
                    <div style={{ marginTop: '1rem' }}>
                      <div style={{
                        fontSize: '0.85rem',
                        fontWeight: 600,
                        color: '#888',
                        marginBottom: '0.5rem',
                        textTransform: 'uppercase'
                      }}>
                        Instructions
                      </div>
                      <div style={{
                        fontSize: '0.9rem',
                        whiteSpace: 'pre-wrap',
                        backgroundColor: '#000',
                        padding: '0.75rem',
                        borderRadius: '4px'
                      }}>
                        {step.instructions}
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  {step.actions && step.actions.length > 0 && (
                    <div style={{ marginTop: '1rem' }}>
                      <div style={{
                        fontSize: '0.85rem',
                        fontWeight: 600,
                        color: '#888',
                        marginBottom: '0.5rem',
                        textTransform: 'uppercase'
                      }}>
                        Actions
                      </div>
                      <ul style={{
                        margin: 0,
                        paddingLeft: '1.5rem',
                        fontSize: '0.9rem',
                        lineHeight: '1.6'
                      }}>
                        {step.actions.map((action, idx) => (
                          <li key={idx}>{action}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
