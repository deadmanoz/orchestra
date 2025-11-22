# Key Architectural Issues - Quick Reference

## Critical Issues (2) 🚨

### 1. MULTIPLE SOURCES OF TRUTH - Data Loss Risk
**Status stored in 3 places with NO sync guarantee:**
- In-memory dict: `/backend/api/workflows.py:24`
- SQLite database: `/backend/db/schema.sql`
- LangGraph checkpoint state (implicit)

**Race Condition:**
```
Memory updated (line 131) → DB update scheduled → CRASH → DB lost, memory lost
```

**Files Affected:**
- `/backend/api/workflows.py:131-140` - Status update with unprotected window
- `/backend/api/workflows.py:263-266` - Identical pattern repeated
- `/backend/api/workflows.py:280-284` - Different query for completion

---

### 2. MEMORY-DB SYNCHRONIZATION RACE CONDITIONS
**Happens in 3 scenarios:**
1. Status updated in memory but not yet in DB when crash occurs
2. Concurrent resume requests on same workflow hit LangGraph simultaneously  
3. WebSocket sends status update before DB is written

**No transaction atomicity** - updates can partially fail

---

## High-Priority Issues (8) ⚠️

### 3. REPEATED STATUS UPDATE CODE (DRY Violation)
**Identical code at lines:**
- 131-140 (after first execution)
- 257-266 (after resume, another checkpoint)

**Identical checkpoint_ready broadcasts at:**
- 143-147
- 269-273

**Extract into:** `mark_workflow_awaiting_checkpoint(workflow_id)`

---

### 4. MISSING CHECKPOINT RESOLUTION PERSISTENCE
**Table exists but never used:**
```sql
CREATE TABLE user_checkpoints (...)  -- Line 17 in schema.sql
```

**But nowhere in code:**
- NO INSERT when checkpoint created
- NO UPDATE when checkpoint resolved
- NO SELECT to query checkpoint history
- History endpoint (line 293) only reads LangGraph state

**Files affected:**
- `/backend/db/schema.sql:17-30` - Defines unused table
- `/backend/api/workflows.py` - No checkpoint writes
- `/backend/workflows/plan_review.py` - No checkpoint writes

---

### 5. CHECKPOINT DATA EXTRACTION COMPLEXITY
**Convoluted extraction at lines 172-203:**
```python
state = await compiled_workflow.aget_state(config)
if state and hasattr(state, 'interrupts') and state.interrupts:
    interrupt_obj = state.interrupts[0]
    if hasattr(interrupt_obj, 'value'):
        pending_checkpoint = interrupt_obj.value
```

**Problems:**
- Relies on LangGraph internals (`state.interrupts`)
- No validation of returned structure
- Multiple format conversions throughout codebase
- Frontend expects different fields than backend returns

---

### 6. ACTIVE WORKFLOWS IN-MEMORY STORE MEMORY LEAK
**At line 24:**
```python
active_workflows = {}  # Never cleaned up!
```

**Issues:**
- No cleanup when workflow completes
- No eviction for long-running workflows  
- Memory grows indefinitely
- Lost on server restart with no recovery
- Used to store: compiled workflow, status, last_result, error

---

### 7. MISSING ABSTRACTION: WorkflowStatusManager
**Status updates scattered across:**
- Line 86, 131, 153 - Direct dict updates
- Line 137-140, 263-266, 280-284 - DB updates in 3 different places
- Frontend in 3 components - Hardcoded status checks

**Should be:** Single service class with atomic operations

---

### 8. MISSING ABSTRACTION: CheckpointManager
**Checkpoint lifecycle duplicated 4 times** in plan_review.py:
1. `_plan_checkpoint_node` (lines 131-155)
2. `_edit_reviewer_prompt_checkpoint_node` (lines 200-224)
3. `_review_checkpoint_node` (lines 308-342)
4. `_edit_planner_prompt_checkpoint_node` (lines 405-429)

**Repeated logic:**
- UUID generation (lines 132, 201, 309, 406)
- Checkpoint data structure creation (4x)
- Human input processing (4x)
- Action routing (4x)

---

### 9. UNRECORDED ERROR STATE
**Failed status NOT persisted to database:**
```python
# Lines 153-154, 290-291
active_workflows[workflow_id]["status"] = WorkflowStatus.FAILED.value
active_workflows[workflow_id]["error"] = str(e)
# ← Missing: database UPDATE!
```

---

### 10. WEAK ERROR HANDLING
**Issues at multiple locations:**
- Bare `except:` blocks (line 64 in websocket.py)
- Print statements instead of logging (lines 149-152, 287-289)
- No retry mechanism for transient errors
- Exception details not persisted

---

## Medium-Priority Issues (12) ⚠️

### 11. HARDCODED STATUS STRINGS IN FRONTEND
**No constants file** - hardcoded checks in:
- `/frontend/src/components/WorkflowDashboard.tsx:44,48,53,76,78,115,122`
- `/frontend/src/hooks/useWorkflow.ts:13`
- `/frontend/src/components/CheckpointEditor.tsx:35-57`

**Problems:**
- Easy to create typos
- Hard to refactor
- 'paused' status (line 53, 178) doesn't exist in backend!

**Should create:** `/frontend/src/constants/workflowStatus.ts`

---

### 12. FRONTEND-BACKEND TYPE MISMATCH
**Backend model** (`/backend/models/checkpoint.py:12-22`):
```python
id, workflow_id, checkpoint_number, step_name, agent_outputs, 
user_edited_content, user_notes, status, created_at, resolved_at
```

**Frontend interface** (`/frontend/src/types/index.ts:32-46`):
```typescript
checkpoint_id (← mismatch: backend uses 'id'),
checkpoint_number, step_name, workflow_id,
iteration (← not in backend), 
agent_outputs (← different structure),
instructions (← not in backend),
actions {primary, secondary[]} (← not in backend),
editable_content (← not in backend),
context
```

---

### 13. STATUS ENUMS FRAGMENTED
**4 different enum locations:**
- WorkflowStatus: `/backend/models/workflow.py:6-12` (6 values)
- CheckpointStatus: `/backend/models/checkpoint.py:6-10` (4 values)
- Agent execution status: `/backend/db/schema.sql:40` (4 values in SQL)
- Agent session status: `/backend/db/schema.sql:55` (4 values in SQL)
- Plan-review internal status: Hard-coded ad-hoc strings (8+ values)

**No shared constants across backend/frontend**

---

### 14. STATUS TRANSITIONS NOT FORMALIZED
**No state machine** to enforce valid transitions

**Currently allowed:**
- Any status → any other status (invalid transitions possible)
- Impossible states not prevented

**Should enforce:**
```
PENDING → RUNNING (only initial)
RUNNING → AWAITING_CHECKPOINT, COMPLETED, FAILED
AWAITING_CHECKPOINT → RUNNING, COMPLETED, FAILED
COMPLETED, FAILED, CANCELLED → (terminal states)
```

---

### 15. WEBSOCKET POLLING INEFFICIENT
**File:** `/backend/api/websocket.py:22-42`

**Issues:**
- Sends status_update every 2 seconds even if nothing changed
- Import inside loop (line 25)
- Duplicates checkpoint_ready broadcast logic (should be one broadcast)
- Only sends when workflow in active_workflows (race condition)

---

## Code Quality Metrics

| Metric | Issue |
|--------|-------|
| **Sources of Truth** | 3 (Memory, DB, LangGraph) |
| **Status Enums** | 4 locations |
| **Duplicated Status Updates** | 2 exact duplicates |
| **Duplicated Checkpoints** | 4 node functions, ~100 LoC duplicate |
| **Hardcoded Status Checks** | 15+ in frontend |
| **Missing Persistence** | Checkpoint resolutions |
| **Memory Leaks** | active_workflows dict |
| **Transaction Coverage** | 0% |
| **Test Coverage** | Unknown (not reviewed) |

---

## Recommended Fixes by Priority

### Phase 1: Critical (Do First!)
1. ✓ Extract `mark_workflow_awaiting_checkpoint()` - fix duplication
2. ✓ Implement atomic database transactions
3. ✓ Add checkpoint resolution persistence  
4. ✓ Fix error status not being recorded
5. ✓ Cleanup active_workflows on workflow completion

### Phase 2: Important (This Sprint)
1. ✓ Create WorkflowStatusManager class
2. ✓ Create CheckpointManager class
3. ✓ Create frontend status constants file
4. ✓ Implement StatusTransitionValidator state machine
5. ✓ Fix type mismatches (checkpoint_id vs id)
6. ✓ Add comprehensive logging (replace print statements)

### Phase 3: Long-term (Next Quarter)
1. ✓ Replace in-memory dict with Redis
2. ✓ Implement event-driven architecture
3. ✓ Add audit trail for all changes
4. ✓ Implement workflow state recovery on restart
5. ✓ Consolidate status enums

---

## Impact Analysis

**If left unfixed, could lead to:**
- Data loss on server crash (CRITICAL)
- Concurrent request handling bugs (HIGH)
- Memory leaks over time (MEDIUM)
- Audit trail gaps (MEDIUM)
- Difficult refactoring when status values change (LOW)

**Estimated effort:**
- Phase 1: 3-4 hours
- Phase 2: 8-10 hours
- Phase 3: 20+ hours

