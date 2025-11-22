# Code Examples of Key Issues

## Issue 1: Multiple Sources of Truth - Code Example

### Location: `/backend/api/workflows.py:131-140` and `263-266`

**Problem: Status stored in 3 places, updated separately**

```python
# Lines 131-132: Update in-memory dict
active_workflows[workflow_id]["status"] = WorkflowStatus.AWAITING_CHECKPOINT.value
active_workflows[workflow_id]["last_result"] = result

# Lines 135-140: Update database AFTER (unprotected window)
async with db.get_connection() as conn:
    await conn.execute(
        "UPDATE workflows SET status = ?, updated_at = ? WHERE id = ?",
        (WorkflowStatus.AWAITING_CHECKPOINT.value, datetime.now().isoformat(), workflow_id)
    )
    await conn.commit()  # ← If crash happens here, memory is stale

# Lines 143-147: Broadcast to WebSocket AFTER
await broadcast_to_workflow(workflow_id, {
    "type": "checkpoint_ready",
    "workflow_id": workflow_id,
    "timestamp": datetime.now().isoformat()
})
```

**The Danger**: If server crashes between lines 131 and 140:
- Memory dict: Lost forever
- Database: Still shows "running" (stale)
- Frontend: May have received checkpoint_ready via WebSocket
- On restart: Database state used, but workflow object gone

**Repeated identically at lines 257-266** - Another DRY violation

---

## Issue 2: Error Status Never Persisted

### Location: `/backend/api/workflows.py:149-154`

```python
except Exception as e:
    print(f"Workflow {workflow_id} failed: {e}")
    import traceback
    traceback.print_exc()
    
    # Lines 153-154: Set in memory only
    active_workflows[workflow_id]["status"] = WorkflowStatus.FAILED.value
    active_workflows[workflow_id]["error"] = str(e)
    
    # ← MISSING: Database UPDATE!
    # Database still shows the old status
```

**Same issue at lines 287-291** in `resume_workflow_execution`

**Result**: 
- User sees failed status in WebSocket message
- Database still shows "running" or "awaiting_checkpoint"
- On restart, old status loaded from DB
- User thinks workflow isn't failed

---

## Issue 3: Duplicated Checkpoint Nodes (100+ LoC duplicate)

### Location: `/backend/workflows/plan_review.py`

**Pattern repeated 4 times identically:**

```python
# Lines 131-155: _plan_checkpoint_node
async def _plan_checkpoint_node(self, state: PlanReviewState) -> dict:
    print(f"[Checkpoint] Plan ready for review - awaiting human approval")

    # Step 1: Create checkpoint (REPEATED 4 TIMES)
    checkpoint_data = {
        "checkpoint_id": str(uuid.uuid4()),          # ← Repeated
        "checkpoint_number": state["checkpoint_number"],  # ← Repeated
        "step_name": "plan_ready_for_review",        # ← Different value
        "workflow_id": state["workflow_id"],         # ← Repeated
        "iteration": state.get("iteration_count", 0), # ← Repeated
        "agent_outputs": [...],                       # ← Repeated pattern
        "instructions": "...",                        # ← Repeated pattern
        "actions": {"primary": "...", "secondary": []}, # ← Repeated
        "editable_content": state["current_plan"]    # ← Repeated
    }

    # Step 2: Interrupt (REPEATED 4 TIMES, line 155)
    human_input = interrupt(checkpoint_data)

    # Step 3: Process decision (REPEATED 4 TIMES)
    action = human_input.get("action", "send_to_reviewers")
    edited_plan = human_input.get("edited_content", state["current_plan"])

    # Step 4: Route based on action (REPEATED 4 TIMES)
    if action == "send_to_reviewers":
        return {
            "user_edits": edited_plan,
            "status": "ready_for_review",      # ← Different status
            "next_step": "review_agents",      # ← Different routing
            "messages": [HumanMessage(...)]
        }
    elif action == "edit_and_continue":
        return {...}
    else:  # cancel
        return {...}


# Lines 200-224: _edit_reviewer_prompt_checkpoint_node (IDENTICAL STRUCTURE)
async def _edit_reviewer_prompt_checkpoint_node(self, state: PlanReviewState) -> dict:
    checkpoint_data = {
        "checkpoint_id": str(uuid.uuid4()),     # ← Same code
        "checkpoint_number": state["checkpoint_number"],  # ← Same code
        "step_name": "edit_reviewer_prompt",    # ← Different value
        "workflow_id": state["workflow_id"],    # ← Same code
        # ... all the same patterns
    }
    human_input = interrupt(checkpoint_data)
    # ... identical processing

# Lines 308-342: _review_checkpoint_node (IDENTICAL)
# Lines 405-429: _edit_planner_prompt_checkpoint_node (IDENTICAL)
```

**Result**: 
- 4x duplicate code to maintain
- If you find a bug in checkpoint processing, must fix in 4 places
- Adding new checkpoint type means copying 50+ lines of code

---

## Issue 4: Hardcoded Status Checks Scattered

### Location: `/frontend/src/components/WorkflowDashboard.tsx:44-132`

```typescript
function getWorkflowStatusMessage(workflow, pendingCheckpoint, executions) {
  // Line 44: Hardcoded string
  if (workflow.status === 'completed') {
    return { message: 'Workflow completed successfully', showSpinner: false };
  }

  // Line 48: Hardcoded string
  if (workflow.status === 'failed') {
    return { message: 'Workflow failed', showSpinner: false };
  }

  // Line 53: WRONG! 'paused' doesn't exist in backend!
  if ((workflow.status === 'paused' || workflow.status === 'awaiting_checkpoint') && pendingCheckpoint) {
    // ...
  }

  // Line 76: Hardcoded string
  if (workflow.status === 'running') {
    // Line 78: Hardcoded status in filter
    const runningAgents = executions.filter(e => e.status === 'running');
    
    // Line 115: Hardcoded status check
    if (lastExecution.agent_type === 'planning' && lastExecution.status === 'completed') {
      // ...
    }

    // Line 122: Hardcoded status in filter
    const recentReviews = sortedExecutions.filter(e => e.agent_type === 'review' && e.status === 'completed');
  }

  return { message: workflow.status, showSpinner: false };
}
```

**Also in: `/frontend/src/hooks/useWorkflow.ts:13`**
```typescript
if (status === 'running' || status === 'awaiting_checkpoint') {
    return 2000;  // Poll more frequently
}
```

**And in: `/frontend/src/components/CheckpointEditor.tsx:35-57`**
```typescript
function getContentLabels(stepName: string, isEditing: boolean) {
  if (stepName === 'edit_reviewer_prompt') {      // ← Hardcoded
    return { title: '...' };
  } else if (stepName === 'edit_planner_prompt') { // ← Hardcoded
    return { title: '...' };
  } else if (stepName === 'reviews_ready_for_consolidation') { // ← Hardcoded
    return { title: '...' };
  }
}
```

**Problems**:
- If you change 'awaiting_checkpoint' to 'paused', must update 5+ files
- Easy to miss one and break UI
- 'paused' status used in UI but doesn't exist in backend!
- No compile-time safety

---

## Issue 5: Type Mismatch Backend vs Frontend

### Location: `/backend/models/checkpoint.py:12-22`

```python
class CheckpointResponse(BaseModel):
    id: str                                  # ← Backend calls it 'id'
    workflow_id: str
    checkpoint_number: int
    step_name: str
    agent_outputs: list[dict]               # ← Simple list of dicts
    user_edited_content: Optional[str] = None
    user_notes: Optional[str] = None
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
```

### Location: `/frontend/src/types/index.ts:32-46`

```typescript
export interface Checkpoint {
  checkpoint_id: string;                    // ← Frontend calls it 'checkpoint_id'!
  checkpoint_number: number;
  step_name: string;
  workflow_id: string;
  iteration: number;                        // ← Not in backend model
  agent_outputs: AgentOutput[];             // ← Expects structured array
  instructions: string;                      // ← Not in backend model
  actions: {                                 // ← Not in backend model
    primary: string;
    secondary: string[];
  };
  editable_content: string;                 // ← Not in backend model
  context?: Record<string, any>;
}
```

**The actual checkpoint data** comes from workflow state (lines 131-152):
```python
checkpoint_data = {
    "checkpoint_id": str(uuid.uuid4()),     # ← Has checkpoint_id
    "checkpoint_number": state["checkpoint_number"],
    "step_name": "plan_ready_for_review",
    "workflow_id": state["workflow_id"],
    "iteration": state.get("iteration_count", 0),
    "agent_outputs": [{                     # ← Structured, not flat
        "agent_name": "planning_agent",
        "agent_type": "planning",
        "output": state["current_plan"],
        "timestamp": datetime.now().isoformat()
    }],
    "instructions": "The PLANNING AGENT...",
    "actions": {
        "primary": "send_to_reviewers",
        "secondary": ["edit_and_continue", "cancel"]
    },
    "editable_content": state["current_plan"]
}
```

**Result**: The actual data matches frontend types better than backend CheckpointResponse!

---

## Issue 6: Status Update Duplication

### Pattern appears at 3 locations:

**Location 1: Lines 137-140**
```python
async with db.get_connection() as conn:
    await conn.execute(
        "UPDATE workflows SET status = ?, updated_at = ? WHERE id = ?",
        (WorkflowStatus.AWAITING_CHECKPOINT.value, datetime.now().isoformat(), workflow_id)
    )
    await conn.commit()
```

**Location 2: Lines 263-266 (IDENTICAL)**
```python
async with db.get_connection() as conn:
    await conn.execute(
        "UPDATE workflows SET status = ?, updated_at = ? WHERE id = ?",  # ← SAME
        (WorkflowStatus.AWAITING_CHECKPOINT.value, datetime.now().isoformat(), workflow_id)  # ← SAME
    )
    await conn.commit()  # ← SAME
```

**Location 3: Lines 280-284 (DIFFERENT)**
```python
async with db.get_connection() as conn:
    await conn.execute(
        "UPDATE workflows SET status = ?, completed_at = ?, updated_at = ? WHERE id = ?",  # ← Different
        (WorkflowStatus.COMPLETED.value, datetime.now().isoformat(),
         datetime.now().isoformat(), workflow_id)  # ← Different
    )
    await conn.commit()
```

**Also duplicated: Checkpoint ready broadcasts at lines 143-147 and 269-273**

---

## Issue 7: Missing Checkpoint Persistence

### Database schema exists (lines 17-30):
```sql
CREATE TABLE IF NOT EXISTS user_checkpoints (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    checkpoint_number INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    agent_outputs JSON NOT NULL,
    user_edited_content TEXT,
    user_notes TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected', 'edited')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_by TEXT,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);
```

### But NEVER used in code:

**File: `/backend/api/workflows.py`**
- No INSERT INTO user_checkpoints
- No UPDATE user_checkpoints  
- No SELECT FROM user_checkpoints

**File: `/backend/workflows/plan_review.py`**
- No database writes
- Checkpoint data only in LangGraph state and return dicts

**Result**:
- Checkpoint history only in LangGraph, not queryable via SQL
- User edits and resolutions lost on server restart
- No audit trail
- API history endpoint (lines 293-355) must read LangGraph, not DB

---

## Issue 8: Active Workflows Memory Leak

### Location: `/backend/api/workflows.py:24`
```python
# In-memory store for active workflows (replace with Redis in production)
active_workflows = {}
```

**Data added at line 83:**
```python
active_workflows[workflow_id] = {
    "compiled": compiled_workflow,           # ← Compiled graph object
    "instance": workflow,                    # ← Workflow instance
    "status": WorkflowStatus.RUNNING.value,  # ← Status string
    "last_result": None                      # ← Latest result dict
}
```

**Data read at:**
- Line 174: `get_workflow` endpoint
- Line 224: `resume_workflow` endpoint  
- Line 298: `get_workflow_history` endpoint
- Line 27: WebSocket polling

**Data cleaned at:**
- ← NOWHERE!

**Result**:
- After workflow completes, entry never removed
- Memory grows forever
- Lost on server restart
- Forces reload of entire workflow state

---

## Issue 9: WebSocket Inefficient Polling

### Location: `/backend/api/websocket.py:22-42`

```python
while True:
    # Import inside loop - inefficient
    from backend.api.workflows import active_workflows
    
    if workflow_id in active_workflows:
        # Create status message with hardcoded type
        status_update = {
            "type": "status_update",
            "workflow_id": workflow_id,
            "status": active_workflows[workflow_id]["status"],  # ← Reads dict
            "timestamp": datetime.now().isoformat()
        }

        try:
            await websocket.send_json(status_update)
        except Exception as e:
            print(f"[WebSocket] Failed to send message: {e}")
            break

    # Sleep 2 seconds, then send again (even if nothing changed!)
    await asyncio.sleep(2)
```

**Problems**:
1. Sends every 2 seconds REGARDLESS of changes
2. Should broadcast on actual state change, not poll
3. Import inside while loop
4. Duplicates checkpoint_ready broadcast logic (lines 143-147, 269-273)

---

## Issue 10: Bare Exception Handlers

### Location 1: `/backend/api/websocket.py:64`
```python
for connection in active_connections[workflow_id]:
    try:
        await connection.send_json(message)
    except:  # ← BARE EXCEPT - catches KeyboardInterrupt, SystemExit, etc!
        dead_connections.append(connection)
```

### Location 2: `/backend/api/workflows.py:149-154`
```python
except Exception as e:
    print(f"Workflow {workflow_id} failed: {e}")  # ← Print instead of logging
    import traceback
    traceback.print_exc()
    active_workflows[workflow_id]["status"] = WorkflowStatus.FAILED.value
    active_workflows[workflow_id]["error"] = str(e)
```

---

## Summary Table

| Issue | Type | Location | Occurrences | LoC Affected |
|-------|------|----------|------------|---|
| Multiple sources of truth | CRITICAL | workflows.py | 3 | 131-140, 263-266, 280-284 |
| Race conditions | CRITICAL | websocket.py | 3 | 25-42 |
| Duplicated status updates | HIGH | workflows.py | 2 | 131-140 & 263-266 |
| Missing checkpoint persistence | HIGH | schema.sql | 1 table unused | 17-30 |
| Hardcoded status checks | MEDIUM | Dashboard.tsx | 15+ | 44-322 |
| Type mismatch | MEDIUM | checkpoint.py & types/index.ts | 1 | Full file |
| Duplicated checkpoint code | MEDIUM | plan_review.py | 4 nodes | 131-429 |

