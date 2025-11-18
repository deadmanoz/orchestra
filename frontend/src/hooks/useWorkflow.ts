import { useQuery } from '@tanstack/react-query';
import { workflowApi } from '../api/client';

export const useWorkflow = (workflowId: string | null) => {
  return useQuery({
    queryKey: ['workflow', workflowId],
    queryFn: () => workflowApi.get(workflowId!),
    enabled: !!workflowId,
    refetchInterval: (query) => {
      // Poll more frequently if workflow is running
      if (query.state.data?.workflow?.status === 'running') {
        return 2000; // 2 seconds
      }
      return false; // Don't poll if completed/failed
    },
  });
};
