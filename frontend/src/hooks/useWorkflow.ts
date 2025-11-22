import { useQuery } from '@tanstack/react-query';
import { workflowApi } from '../api/client';
import { isActiveStatus } from '../constants/workflowStatus';

export const useWorkflow = (workflowId: string | null) => {
  return useQuery({
    queryKey: ['workflow', workflowId],
    queryFn: () => workflowApi.get(workflowId!),
    enabled: !!workflowId,
    refetchInterval: (query) => {
      const status = query.state.data?.workflow?.status;
      // Poll more frequently if workflow is active (running or awaiting checkpoint)
      if (status && isActiveStatus(status)) {
        return 2000; // 2 seconds
      }
      return false; // Don't poll if completed/failed
    },
  });
};
