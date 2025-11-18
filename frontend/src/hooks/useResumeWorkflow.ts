import { useMutation, useQueryClient } from '@tanstack/react-query';
import { workflowApi } from '../api/client';
import type { CheckpointResolution } from '../types';

export const useResumeWorkflow = (workflowId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (resolution: CheckpointResolution) =>
      workflowApi.resume(workflowId, resolution),
    onSuccess: () => {
      // Invalidate and refetch workflow data
      queryClient.invalidateQueries({ queryKey: ['workflow', workflowId] });
    },
  });
};
