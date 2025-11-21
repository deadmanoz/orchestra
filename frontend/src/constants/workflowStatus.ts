/**
 * Workflow Status Constants
 *
 * Centralized workflow status values shared across the frontend.
 * These must match the backend WorkflowStatus enum values.
 */

export const WorkflowStatus = {
  PENDING: 'pending',
  RUNNING: 'running',
  AWAITING_CHECKPOINT: 'awaiting_checkpoint',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const;

export type WorkflowStatusType = typeof WorkflowStatus[keyof typeof WorkflowStatus];

/**
 * Checkpoint Step Names
 *
 * Standard checkpoint step identifiers.
 */
export const CheckpointStep = {
  PLAN_READY_FOR_REVIEW: 'plan_ready_for_review',
  EDIT_REVIEWER_PROMPT: 'edit_reviewer_prompt',
  REVIEWS_READY_FOR_CONSOLIDATION: 'reviews_ready_for_consolidation',
  EDIT_PLANNER_PROMPT: 'edit_planner_prompt',
} as const;

export type CheckpointStepType = typeof CheckpointStep[keyof typeof CheckpointStep];

/**
 * Checkpoint Actions
 *
 * Standard actions available at checkpoints.
 */
export const CheckpointAction = {
  SEND_TO_REVIEWERS: 'send_to_reviewers',
  SEND_TO_PLANNER_FOR_REVISION: 'send_to_planner_for_revision',
  EDIT_AND_CONTINUE: 'edit_and_continue',
  EDIT_FULL_PROMPT: 'edit_full_prompt',
  REQUEST_REVISION: 'request_revision',
  EDIT_PROMPT_AND_REVISE: 'edit_prompt_and_revise',
  APPROVE_PLAN: 'approve_plan',
  APPROVE: 'approve',
  CANCEL: 'cancel',
} as const;

export type CheckpointActionType = typeof CheckpointAction[keyof typeof CheckpointAction];

/**
 * Helper function to check if status is terminal (workflow ended)
 */
export function isTerminalStatus(status: string): boolean {
  return status === WorkflowStatus.COMPLETED ||
         status === WorkflowStatus.FAILED ||
         status === WorkflowStatus.CANCELLED;
}

/**
 * Helper function to check if status is active (workflow can be interacted with)
 */
export function isActiveStatus(status: string): boolean {
  return status === WorkflowStatus.RUNNING ||
         status === WorkflowStatus.AWAITING_CHECKPOINT;
}

/**
 * Get human-readable status label
 */
export function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    [WorkflowStatus.PENDING]: 'Pending',
    [WorkflowStatus.RUNNING]: 'Running',
    [WorkflowStatus.AWAITING_CHECKPOINT]: 'Awaiting Input',
    [WorkflowStatus.COMPLETED]: 'Completed',
    [WorkflowStatus.FAILED]: 'Failed',
    [WorkflowStatus.CANCELLED]: 'Cancelled',
  };
  return labels[status] || status;
}

/**
 * Get checkpoint step label
 */
export function getCheckpointStepLabel(stepName: string): string {
  const labels: Record<string, string> = {
    [CheckpointStep.PLAN_READY_FOR_REVIEW]: 'Plan Ready for Review',
    [CheckpointStep.EDIT_REVIEWER_PROMPT]: 'Edit Reviewer Prompt',
    [CheckpointStep.REVIEWS_READY_FOR_CONSOLIDATION]: 'Reviews Ready',
    [CheckpointStep.EDIT_PLANNER_PROMPT]: 'Edit Planner Prompt',
  };
  return labels[stepName] || stepName;
}
