INVESTIGATE the Task Center codebase for bugs and issues. DO NOT change any design. Only find and fix bugs.

## Scope
- backend/app/services/ related to tasks
- backend/app/api/routes/tasks.py
- backend/app/api/routes/task_center.py
- backend/app/repositories/ (task-related)
- frontend/src/ (task center components)
- tests/ (task-related tests)

## Investigation Method
1. Read the task center domain doc: memory-bank/knowledge/domains/task-center.md
2. Read ADRs related to tasks
3. Scan the code for:
   - Race conditions (missing FOR UPDATE, wrong lock order)
   - State machine violations (invalid transitions)
   - Authorization gaps (missing permission checks)
   - Data integrity (orphaned records, missing cascades)
   - Error handling (swallowed exceptions, wrong HTTP codes)
   - Frontend state bugs (stale data, missing loading/error states)
4. Run tests and check for any failing task-related tests

## Output
After investigation, list ALL bugs found with:
- File + line number
- Bug description
- Severity (P0/P1/P2)
- Whether it can be fixed without design change

Then fix all P0 and P1 bugs. Do NOT touch design or architecture.