import { useQuery } from '@tanstack/react-query';
import { workflowApi } from '../api/client';

export const useWorkflow = (workflowId: string | null) => {
  return useQuery({
    queryKey: ['workflow', workflowId],
    queryFn: () => workflowApi.get(workflowId!),
    enabled: !!workflowId,
    refetchInterval: (query) => {
      const status = query.state.data?.workflow?.status;
      // Poll more frequently if workflow is running or awaiting checkpoint
      // (awaiting_checkpoint means it could transition to next checkpoint after user action)
      if (status === 'running' || status === 'awaiting_checkpoint') {
        return 2000; // 2 seconds
      }
      return false; // Don't poll if completed/failed
    },
  });
};
