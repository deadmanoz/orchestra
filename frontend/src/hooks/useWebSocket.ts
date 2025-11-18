import { useEffect, useRef, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { WorkflowWebSocket } from '../api/client';

export const useWebSocket = (workflowId: string | null) => {
  const wsRef = useRef<WorkflowWebSocket | null>(null);
  const queryClient = useQueryClient();

  const handleStatusUpdate = useCallback((_message: any) => {
    // Invalidate workflow query to trigger refetch
    queryClient.invalidateQueries({ queryKey: ['workflow', workflowId] });
  }, [workflowId, queryClient]);

  const handleCheckpointReady = useCallback((_message: any) => {
    // Invalidate workflow query to show new checkpoint
    queryClient.invalidateQueries({ queryKey: ['workflow', workflowId] });
  }, [workflowId, queryClient]);

  useEffect(() => {
    if (!workflowId) return;

    wsRef.current = new WorkflowWebSocket().connect(workflowId);
    wsRef.current.on('status_update', handleStatusUpdate);
    wsRef.current.on('checkpoint_ready', handleCheckpointReady);

    return () => {
      wsRef.current?.disconnect();
    };
  }, [workflowId, handleStatusUpdate, handleCheckpointReady]);

  return wsRef.current;
};
