import { useMutation } from '@tanstack/react-query';
import { workflowApi } from '../api/client';
import type { WorkflowCreate } from '../types';

export const useCreateWorkflow = () => {
  return useMutation({
    mutationFn: (data: WorkflowCreate) => workflowApi.create(data),
  });
};
