# Comprehensive Architectural Review: Checkpointing System

## Executive Summary
The checkpointing system has several systemic architectural issues that create maintenance challenges and potential race conditions. The main problems are scattered status management, multiple sources of truth, code duplication, and missing abstractions around checkpoint and workflow lifecycle management.

---

## 1. DATA FLOW & STATE MANAGEMENT

### 1.1 Multiple Sources of Truth [CRITICAL]

**Issue**: Workflow status is stored in THREE places with NO synchronization guarantee:
1. `active_workflows` in-memory dict (`backend/api/workflows.py:24`)
2. SQLite database (`workflows` table)
3. LangGraph checkpoint state (implicit)

**Locations**:
- **Memory**: `/home/user/orchestra/backend/api/workflows.py:24` - `active_workflows = {}`
- **Database**: `/home/user/orchestra/backend/api/workflows.py:59` - INSERT and lines 137, 263, 280 - UPDATE
- **LangGraph**: `/home/user/orchestra/backend/workflows/plan_review.py:40` - AsyncSqliteSaver

**Problem Scenario**: 
```
1. Workflow starts, status set to "running" in memory and DB (lines 66, 86, 101)
2. First checkpoint hit, status updated in memory (line 131)
3. Database updated AFTER (line 137-140)
4. If crash between memory update and DB write → inconsistent state
5. On restart, memory state lost, but DB used (no recovery logic visible)
```

**Evidence**:
```python
# Line 131 - Updates memory FIRST
active_workflows[workflow_id]["status"] = WorkflowStatus.AWAITING_CHECKPOINT.value

# Lines 135-140 - Updates DB AFTER (unprotected window)
async with db.get_connection() as conn:
    await conn.execute(
        "UPDATE workflows SET status = ?, updated_at = ? WHERE id = ?",
        (WorkflowStatus.AWAITING_CHECKPOINT.value, datetime.now().isoformat(), workflow_id)
    )
    await conn.commit()
```

**Severity**: CRITICAL

**Impact**: 
- Race conditions possible if multiple requests hit simultaneously
- No atomicity between memory and database
- Server crash loses in-flight state
- WebSocket clients may see stale status

---

### 1.2 Checkpoint Data Extraction Complexity [HIGH]

**Issue**: Checkpoint data extraction from LangGraph interrupt is convoluted with multiple format conversions:

**File**: `/home/user/orchestra/backend/api/workflows.py:172-203`

```python
# Line 182-195: Complex extraction logic
state = await compiled_workflow.aget_state(config)
if state and hasattr(state, 'interrupts') and state.interrupts:
    interrupt_obj = state.interrupts[0]
    if hasattr(interrupt_obj, 'value'):
        pending_checkpoint = interrupt_obj.value
```

**Problems**:
1. Relies on internal LangGraph structure (`state.interrupts`)
2. No type checking on `interrupt_obj.value`
3. Multiple `.get()` calls with defaults scatter throughout codebase
4. No validation of checkpoint data structure
5. Frontend expects different structure than what's extracted

**Data Flow Mismatch**:
```
Backend returns (from aget_state):
{
  checkpoint_id, checkpoint_number, step_name, 
  agent_outputs, instructions, actions, editable_content
}

Frontend expects (from types/index.ts):
{
  checkpoint_id, checkpoint_number, step_name,
  iteration, workflow_id, agent_outputs[], instructions,
  actions {primary, secondary[]}, editable_content, context
}
```

**Severity**: HIGH

**Locations**:
- Extraction: `/home/user/orchestra/backend/api/workflows.py:172-203`
- Frontend types: `/home/user/orchestra/frontend/src/types/index.ts:32-46`
- Backend models: `/home/user/orchestra/backend/models/checkpoint.py:12-22`

---

### 1.3 Missing Checkpoint Resolution Persistence [HIGH]

**Issue**: Checkpoint resolutions are never recorded to database, only LangGraph state

**Evidence**:
- `user_checkpoints` table exists in schema (`/home/user/orchestra/backend/db/schema.sql:17-30`)
- Table includes fields: `status`, `user_edited_content`, `user_notes`, `resolved_at`
- But NO INSERT/UPDATE code for this table exists in codebase
- Checkpoint resolutions only exist in LangGraph state and memory

**Affected Locations**:
- Schema defines table: `/home/user/orchestra/backend/db/schema.sql:17-30`
- Never used in: `/home/user/orchestra/backend/api/workflows.py` (entire file)
- Never used in: `/home/user/orchestra/backend/workflows/plan_review.py` (entire file)

**Severity**: HIGH

**Impact**:
- Audit trail lost
- Cannot query checkpoint history from database
- Resume logic not persisted
- API `/history` endpoint only reads LangGraph state (lines 293-355)

---

### 1.4 Inconsistent State Updates Between Functions [HIGH]

**Issue**: Same update pattern repeated 3 times, inconsistently

**File**: `/home/user/orchestra/backend/api/workflows.py`

**Pattern 1 - Lines 131-140** (after first execution):
```python
active_workflows[workflow_id]["status"] = WorkflowStatus.AWAITING_CHECKPOINT.value
active_workflows[workflow_id]["last_result"] = result
# Then UPDATE database
```

**Pattern 2 - Lines 257-266** (after resume, hit another checkpoint):
```python
active_workflows[workflow_id]["status"] = WorkflowStatus.AWAITING_CHECKPOINT.value
active_workflows[workflow_id]["last_result"] = result
# Then UPDATE database (SAME SQL)
```

**Pattern 3 - Lines 276-284** (after resume, workflow completed):
```python
active_workflows[workflow_id]["status"] = WorkflowStatus.COMPLETED.value
# Different UPDATE query (includes completed_at)
```

**Pattern 4 - Lines 153-154, 290-291** (on error):
```python
active_workflows[workflow_id]["status"] = WorkflowStatus.FAILED.value
active_workflows[workflow_id]["error"] = str(e)
# NO database update!
```

**DRY Violations**:
- Lines 131 & 257: Identical status update logic
- Lines 137-140 & 263-266: Identical UPDATE queries
- Lines 143-147 & 269-273: Identical checkpoint_ready broadcast

**Severity**: HIGH

---

## 2. STATUS MANAGEMENT

### 2.1 Hardcoded Status Strings in Frontend [MEDIUM]

**File**: `/home/user/orchestra/frontend/src/components/WorkflowDashboard.tsx`

**Hardcoded Checks**:
```typescript
// Line 44
if (workflow.status === 'completed') { ... }

// Line 48  
if (workflow.status === 'failed') { ... }

// Line 53 - WRONG! No 'paused' status exists in backend
if ((workflow.status === 'paused' || workflow.status === 'awaiting_checkpoint') && pendingCheckpoint) { ... }

// Line 76
if (workflow.status === 'running') { ... }

// Line 78
const runningAgents = executions.filter(e => e.status === 'running');

// Line 115, 122
if (lastExecution.agent_type === 'planning' && lastExecution.status === 'completed') { ... }
```

**Additional Issues**:
- `useWorkflow.ts:13`: `status === 'running' || status === 'awaiting_checkpoint'` (hardcoded)
- `CheckpointEditor.tsx:35-57`: Step name hardcoded checks (edit_reviewer_prompt, edit_planner_prompt, etc.)

**Severity**: MEDIUM

**Problems**:
1. No constants file in TypeScript
2. Easy to create typos
3. Hard to refactor status values
4. Inconsistent with backend enums
5. 'paused' status doesn't exist in backend

---

### 2.2 Status Enum Fragmentation [MEDIUM]

**Locations**:
- **Workflow Status**: `/home/user/orchestra/backend/models/workflow.py:6-12`
  ```python
  PENDING = "pending"
  RUNNING = "running"
  AWAITING_CHECKPOINT = "awaiting_checkpoint"
  COMPLETED = "completed"
  FAILED = "failed"
  CANCELLED = "cancelled"
  ```

- **Checkpoint Status**: `/home/user/orchestra/backend/models/checkpoint.py:6-10`
  ```python
  PENDING = "pending"
  APPROVED = "approved"
  REJECTED = "rejected"
  EDITED = "edited"
  ```

- **Agent Execution Status**: `/home/user/orchestra/backend/db/schema.sql:40`
  ```sql
  CHECK(status IN ('pending', 'running', 'completed', 'failed'))
  ```

- **Agent Session Status**: `/home/user/orchestra/backend/db/schema.sql:55`
  ```sql
  CHECK(status IN ('starting', 'running', 'stopped', 'error'))
  ```

**Problems**:
1. Multiple status enums for different entities
2. No shared constants across backend/frontend
3. Status values hardcoded in SQL CHECK constraints
4. Plan-Review workflow uses ad-hoc status strings:
   - `"plan_created"` (line 122)
   - `"ready_for_review"` (line 165)
   - `"editing_reviewer_prompt"` (line 175)
   - `"reviews_collected"` (line 291)
   - `"approved"` (line 349)
   - `"revision_needed"` (line 358)
   - `"editing_planner_prompt"` (line 369)
   - `"cancelled"` (line 184, 242, 379)

**Severity**: MEDIUM

---

### 2.3 Status Transitions Not Centralized [MEDIUM]

**Issue**: Status transitions scattered across multiple functions

**Valid Transitions** (inferred from code):
```
PENDING → RUNNING (line 66, 101 create_workflow)
RUNNING → AWAITING_CHECKPOINT (line 131, 257)
AWAITING_CHECKPOINT → RUNNING (line 131 on resume)
AWAITING_CHECKPOINT → COMPLETED (line 276)
AWAITING_CHECKPOINT → FAILED (line 290)
RUNNING → FAILED (line 153)
```

**Internal Workflow Status** (plan_review.py):
```
starting → plan_created → ready_for_review → editing_reviewer_prompt
→ reviews_collected → approved/revision_needed/editing_planner_prompt
→ cancelled
```

**Problem**: 
- No state machine to enforce valid transitions
- Impossible states not prevented (e.g., COMPLETED → AWAITING_CHECKPOINT)
- Business logic scattered across 3 files:
  - `/home/user/orchestra/backend/api/workflows.py`
  - `/home/user/orchestra/backend/workflows/plan_review.py`
  - `/home/user/orchestra/frontend/src/components/WorkflowDashboard.tsx`

**Severity**: MEDIUM

---

## 3. CODE DUPLICATION (DRY VIOLATIONS)

### 3.1 Repeated Status Update Pattern [HIGH]

**File**: `/home/user/orchestra/backend/api/workflows.py`

**Duplication 1**: Lines 131-140 and 257-266
```python
# EXACT DUPLICATE CODE
active_workflows[workflow_id]["status"] = WorkflowStatus.AWAITING_CHECKPOINT.value
active_workflows[workflow_id]["last_result"] = result

async with db.get_connection() as conn:
    await conn.execute(
        "UPDATE workflows SET status = ?, updated_at = ? WHERE id = ?",
        (WorkflowStatus.AWAITING_CHECKPOINT.value, datetime.now().isoformat(), workflow_id)
    )
    await conn.commit()
```

**Duplication 2**: Lines 143-147 and 269-273
```python
# EXACT DUPLICATE WEBSOCKET BROADCAST
await broadcast_to_workflow(workflow_id, {
    "type": "checkpoint_ready",
    "workflow_id": workflow_id,
    "timestamp": datetime.now().isoformat()
})
```

**Severity**: HIGH

**Extraction Opportunity**:
```python
async def mark_workflow_awaiting_checkpoint(workflow_id: str, result: dict):
    """Centralized status update for checkpoint"""
    active_workflows[workflow_id]["status"] = WorkflowStatus.AWAITING_CHECKPOINT.value
    active_workflows[workflow_id]["last_result"] = result
    
    async with db.get_connection() as conn:
        await conn.execute(
            "UPDATE workflows SET status = ?, updated_at = ? WHERE id = ?",
            (WorkflowStatus.AWAITING_CHECKPOINT.value, datetime.now().isoformat(), workflow_id)
        )
        await conn.commit()
    
    await broadcast_to_workflow(workflow_id, {
        "type": "checkpoint_ready",
        "workflow_id": workflow_id,
        "timestamp": datetime.now().isoformat()
    })
```

---

### 3.2 Repeated Checkpoint Data Structure [MEDIUM]

**File**: `/home/user/orchestra/backend/workflows/plan_review.py`

**Duplication in checkpoint nodes**:
Lines 131-152, 200-221, 308-339, 405-426

**Common Pattern**:
```python
checkpoint_data = {
    "checkpoint_id": str(uuid.uuid4()),
    "checkpoint_number": state["checkpoint_number"],
    "step_name": "...",
    "workflow_id": state["workflow_id"],
    "iteration": state.get("iteration_count", 0),
    "agent_outputs": [...],
    "instructions": "...",
    "actions": {"primary": "...", "secondary": [...]},
    "editable_content": "..."
}
human_input = interrupt(checkpoint_data)
action = human_input.get("action", "default")
```

**Appears 4 Times**:
1. `_plan_checkpoint_node` (lines 131-155)
2. `_edit_reviewer_prompt_checkpoint_node` (lines 200-224)
3. `_review_checkpoint_node` (lines 308-342)
4. `_edit_planner_prompt_checkpoint_node` (lines 405-429)

**Severity**: MEDIUM

---

### 3.3 Status Field Duplication [MEDIUM]

**File**: `/home/user/orchestra/backend/workflows/plan_review.py`

**Returned status values** appear in every checkpoint and agent node:
```python
# Lines 122, 165, 175, 184, 291, 349, 358, 369, 379, 438, 448
return {
    "status": "...",
    # ... other fields
}
```

**Always paired with `next_step`**:
```python
# Lines 166, 176, 185, 239, 243, 350, 359, 370, 380
"next_step": "..."
```

**Severity**: MEDIUM

**Impact**: Hard to refactor status values

---

## 4. DESIGN ISSUES

### 4.1 No Clear Separation of Concerns [HIGH]

**Problem**: Checkpoint lifecycle responsibilities scattered

**File**: `/home/user/orchestra/backend/workflows/plan_review.py`

Each checkpoint node does:
1. Create checkpoint data structure (lines 131-152, etc.)
2. Call interrupt() to pause (lines 155, 224, 342, 429)
3. Validate human input (lines 158-159, 227-228, 344-345, 432-433)
4. Route based on action (lines 162-190, 230-248, 347-385, 435-454)
5. Update state (return dict with status, next_step, etc.)

**Better Design**: 
- Checkpoint manager should handle creation & data structure
- Route manager should handle action routing
- State updater should handle state transitions

---

### 4.2 Type Mismatch Between Backend and Frontend [MEDIUM]

**Backend Checkpoint Model** (`/home/user/orchestra/backend/models/checkpoint.py:12-22`):
```python
class CheckpointResponse(BaseModel):
    id: str
    workflow_id: str
    checkpoint_number: int
    step_name: str
    agent_outputs: list[dict]
    user_edited_content: Optional[str] = None
    user_notes: Optional[str] = None
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
```

**Frontend Checkpoint Interface** (`/home/user/orchestra/frontend/src/types/index.ts:32-46`):
```typescript
export interface Checkpoint {
  checkpoint_id: string;           // ← Backend uses 'id'
  checkpoint_number: number;
  step_name: string;
  workflow_id: string;
  iteration: number;               // ← Not in backend model
  agent_outputs: AgentOutput[];    // ← Different structure
  instructions: string;            // ← Not in backend model
  actions: {primary: string; secondary: string[]}; // ← Not in backend model
  editable_content: string;        // ← Not in backend model
  context?: Record<string, any>;
}
```

**Severity**: MEDIUM

**Impact**: API response doesn't match frontend expectations, requires ad-hoc conversion

---

### 4.3 Active Workflows In-Memory Store Lacks Lifecycle Management [HIGH]

**File**: `/home/user/orchestra/backend/api/workflows.py:24`

```python
active_workflows = {}
```

**Issues**:
1. No cleanup when workflow completes
2. No eviction for long-running workflows
3. Memory grows indefinitely
4. No way to recover state on server restart
5. No serialization mechanism
6. Used to track: compiled workflow, status, last_result, error

**Locations where data added**:
- Line 83-87: Initial creation

**Locations where data read**:
- Lines 174-203: get_workflow endpoint
- Lines 224-237: resume_workflow endpoint
- Lines 298-355: get_workflow_history endpoint
- Lines 25, 27, 31: websocket.py polling

**No cleanup anywhere** - memory leak potential

**Severity**: HIGH

---

### 4.4 Weak Error Handling [MEDIUM]

**File**: `/home/user/orchestra/backend/api/workflows.py`

**Issues**:
1. Error status set but not persisted to DB (lines 153, 290)
   ```python
   active_workflows[workflow_id]["status"] = WorkflowStatus.FAILED.value
   active_workflows[workflow_id]["error"] = str(e)
   # Missing: await conn.execute("UPDATE workflows SET status=?", ...)
   ```

2. Exception handling at lines 149-154:
   ```python
   except Exception as e:
       print(f"Workflow {workflow_id} failed: {e}")
       import traceback
       traceback.print_exc()
       # Bare print statements - no logging
   ```

3. No retry mechanism for transient errors

4. WebSocket errors silently continue (lines 64 in websocket.py)
   ```python
   except:  # BARE EXCEPT!
       dead_connections.append(connection)
   ```

**Severity**: MEDIUM

---

### 4.5 WebSocket Polling Architecture [MEDIUM]

**File**: `/home/user/orchestra/backend/api/websocket.py:22-42`

**Issues**:
```python
while True:
    from backend.api.workflows import active_workflows  # ← Import inside loop!
    
    if workflow_id in active_workflows:
        status_update = {
            "type": "status_update",
            "status": active_workflows[workflow_id]["status"],
            "timestamp": datetime.now().isoformat()
        }
        try:
            await websocket.send_json(status_update)
        except Exception as e:
            print(f"[WebSocket] Failed to send message: {e}")
            break
    
    await asyncio.sleep(2)  # ← Sends every 2 seconds even if nothing changed
```

**Problems**:
1. Sends status_update every 2 seconds regardless of changes
2. Should use broadcast mechanism for actual changes, not polling
3. Import inside loop inefficient
4. Only sends when workflow in active_workflows dict (race condition window)
5. Duplicates checkpoint_ready broadcast logic

**Severity**: MEDIUM

---

## 5. MISSING ABSTRACTIONS

### 5.1 Missing WorkflowStatusManager Service [HIGH]

**Needed**: Centralized class to manage all status-related operations

**Current scattered logic**:
- Direct dict updates (lines 86, 131, 153, 257, 276, 290)
- Direct database updates (lines 137-140, 263-266, 280-284)
- Conditional logic in three places (Dashboard, useWorkflow, etc.)

**Should be**:
```python
class WorkflowStatusManager:
    async def initialize(self, workflow_id, workflow_type):
        """Set initial status"""
        
    async def mark_awaiting_checkpoint(self, workflow_id):
        """Atomically update memory + DB + broadcast"""
        
    async def mark_completed(self, workflow_id):
        """Handle completion"""
        
    async def mark_failed(self, workflow_id, error):
        """Handle failure"""
        
    def is_valid_transition(self, current_status, new_status):
        """Validate state machine"""
```

---

### 5.2 Missing CheckpointManager Class [HIGH]

**Needed**: Centralized checkpoint lifecycle management

**Current scattered logic**:
- 4 separate checkpoint node functions with duplicate structure
- Manual UUID generation (4 times)
- Manual checkpoint_data dict creation (4 times)
- Human input validation repeated (4 times)
- Action routing scattered in each node (4 times)

**Should be**:
```python
class CheckpointManager:
    async def create_checkpoint(self, state, step_name, agent_outputs, instructions, actions):
        """Create and interrupt"""
        
    async def process_resolution(self, human_input, state):
        """Validate and route action"""
        
    async def persist_to_db(self, checkpoint_data, resolution):
        """Store in user_checkpoints table"""
```

---

### 5.3 Missing Constants File (Frontend) [MEDIUM]

**Needed**: TypeScript constants for status values

**Should create**: `/home/user/orchestra/frontend/src/constants/workflowStatus.ts`

```typescript
export const WORKFLOW_STATUS = {
  PENDING: 'pending',
  RUNNING: 'running',
  AWAITING_CHECKPOINT: 'awaiting_checkpoint',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const;

export const EXECUTION_STATUS = {
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
} as const;

export const STEP_NAMES = {
  PLAN_READY: 'plan_ready_for_review',
  EDIT_REVIEWER_PROMPT: 'edit_reviewer_prompt',
  REVIEWS_READY: 'reviews_ready_for_consolidation',
  EDIT_PLANNER_PROMPT: 'edit_planner_prompt',
} as const;
```

---

### 5.4 Missing StatusTransitionValidator [MEDIUM]

**Needed**: Enforce valid status transitions

**Current**: Any status can follow any other status

**Should implement**: State machine to validate:
```
PENDING → RUNNING (only valid initial transition)
RUNNING → AWAITING_CHECKPOINT (when checkpoint hit)
RUNNING → COMPLETED (rare, if no checkpoints)
RUNNING → FAILED (on error)
AWAITING_CHECKPOINT → RUNNING (on resume)
AWAITING_CHECKPOINT → COMPLETED (on final approval)
AWAITING_CHECKPOINT → FAILED (on error)
COMPLETED, FAILED, CANCELLED → (no transitions)
```

---

### 5.5 Missing Utility Functions [MEDIUM]

**Needed**:
```typescript
// Frontend
export function isWorkflowRunning(status: string): boolean
export function shouldPollWorkflow(status: string): boolean
export function isCheckpointPending(status: string, checkpoint: Checkpoint | null): boolean

// Backend
async def update_workflow_status(workflow_id, new_status, **kwargs):
    """Atomic status update with DB + memory sync"""
    
async def record_checkpoint_resolution(workflow_id, checkpoint_id, resolution):
    """Persist checkpoint resolution to database"""
```

---

## 6. RACE CONDITIONS & CONSISTENCY ISSUES

### 6.1 Memory-DB Sync Window [CRITICAL]

**File**: `/home/user/orchestra/backend/api/workflows.py`

**Race Condition 1: Status Update Gap** (Lines 131-140)
```
T1: Memory updated
T1+Δt: DB scheduled (but not yet written)
T1+2Δt: Server crashes before commit
→ DB still shows RUNNING, memory lost
→ Restart loads DB (shows RUNNING), but workflow object gone
```

**Race Condition 2: Concurrent Resume Requests** (Lines 216-239)
```
T1: Request A calls resume_workflow
T1+Δt: Request B calls resume_workflow (same workflow_id)
→ Both read same workflow state from LangGraph
→ Both execute resume logic
→ LangGraph may apply both resumes (unclear behavior)
→ Inconsistent state
```

**Race Condition 3: WebSocket Timing** (websocket.py)
```
T1: Workflow hits checkpoint, status updated in memory
T1+Δt: WebSocket sends status_update (shows new status)
T1+2Δt: Database finally written
T1+3Δt: Server crashes before DB commit
→ Frontend believes status updated, but DB lost it
```

---

### 6.2 Missing Transaction Atomicity [HIGH]

**File**: `/home/user/orchestra/backend/api/workflows.py`

All database updates lack atomicity:
```python
# Line 137-140 - Can partially fail
await conn.execute(...)
await conn.commit()  # ← If this fails, previous state corrupted
```

**Better approach**:
```python
async with db.transaction() as conn:
    await conn.execute(...)
    # Auto-rollback on exception
```

---

## SUMMARY OF ISSUES BY SEVERITY

| Severity | Count | Issues |
|----------|-------|--------|
| **CRITICAL** | 2 | Multiple sources of truth; Memory-DB sync race conditions |
| **HIGH** | 8 | DB update duplication; Missing checkpoint persistence; Checkpoint extraction complexity; Active workflows lifecycle; Status manager needed; Checkpoint manager needed |
| **MEDIUM** | 12 | Hardcoded status strings; Enum fragmentation; Status transitions not centralized; DRY violations; Type mismatches; Error handling; WebSocket polling; Constants needed; State validator needed; Utility functions; Transaction atomicity |

---

## RECOMMENDED ARCHITECTURAL IMPROVEMENTS

### Phase 1: Critical Fixes (Prevent Data Loss)
1. Implement atomic database updates with transactions
2. Create WorkflowStatusManager to sync memory + DB
3. Add checkpoint resolution persistence
4. Implement proper error status in database

### Phase 2: Design Improvements (Maintainability)
1. Create CheckpointManager to eliminate duplicate node logic
2. Centralize status constants (backend + frontend)
3. Implement StatusTransitionValidator state machine
4. Fix type mismatches between backend/frontend

### Phase 3: Long-term Architecture
1. Replace in-memory active_workflows with Redis (for distributed systems)
2. Implement event-driven architecture for status changes
3. Create comprehensive audit trail for all workflow changes
4. Add workflow state recovery on startup

