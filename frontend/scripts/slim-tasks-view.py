"""Slim TasksView.vue — workspace only, detail via TaskDetailShell."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS_VIEW = ROOT / "src/views/TasksView.vue"

content = TASKS_VIEW.read_text(encoding="utf-8")

# --- Extract sections ---
script_match = re.search(r"<script setup lang=\"ts\">(.*?)</script>", content, re.S)
template_match = re.search(
    r"</script>\s*<template>(.*)</template>\s*<style scoped>",
    content,
    re.S,
)
style_match = re.search(r"<style scoped>(.*?)</style>", content, re.S)
if not script_match or not template_match or not style_match:
    raise SystemExit("Failed to parse TasksView.vue")

script = script_match.group(1)
template = template_match.group(1)
style = style_match.group(1)

# --- Script: drop detail-only props and detail state/handlers ---
script = re.sub(
    r"interface Props \{.*?\}",
    """interface Props {
  showCreateTaskComposer?: boolean
  initialSelectedTaskId?: string
  delegateUserOptions?: TaskCenterUserOption[]
  hideStats?: boolean
  hideViewToggle?: boolean
  externalViewMode?: 'list' | 'board' | 'gantt'
}""",
    script,
    count=1,
    flags=re.S,
)

script = re.sub(
    r"const props = withDefaults\(defineProps<Props>\(\), \{.*?\}\)",
    """const props = withDefaults(defineProps<Props>(), {
  showCreateTaskComposer: true,
  delegateUserOptions: () => [],
  hideStats: false,
  hideViewToggle: false,
})""",
    script,
    count=1,
    flags=re.S,
)

# Remove detail-specific imports
for imp in [
    "import { listAttachments, uploadAttachment } from '@/api/attachments'\n",
    "import AttachmentActions from '@/components/attachments/AttachmentActions.vue'\n",
    "import { ATTACHMENT_ACCEPT, validateAttachmentFile } from '@/constants/attachments'\n",
    "import BatchRunDashboard from '@/components/workflow/BatchRunDashboard.vue'\n",
    "import TemplateAggregatePanel from '@/components/workflow/TemplateAggregatePanel.vue'\n",
    "import VideoCapturePanel from '@/components/workflow/VideoCapturePanel.vue'\n",
    "import VideoCaptureProgressPanel from '@/components/workflow/VideoCaptureProgressPanel.vue'\n",
    "import VideoProductionPanel from '@/components/workflow/VideoProductionPanel.vue'\n",
    "import VideoTrackingPanel from '@/components/workflow/VideoTrackingPanel.vue'\n",
    "import TaskDetailMoreMenu from '@/components/task-detail/TaskDetailMoreMenu.vue'\n",
    "import {\n  isVideoWorkflowProfile,\n  resolveTaskDetailProfile,\n} from '@/domain/task-detail/profile'\n",
    "import { resolveTaskRunLabel } from '@/domain/task-detail/run-label'\n",
    "import {\n  resolveTaskUserFacingStateForTask,\n  TASK_USER_FACING_STATE_LABELS,\n  userFacingStateTagType,\n} from '@/domain/task-detail/user-state'\n",
    "import { decideStepRun } from '@/api/task-templates'\n",
    "import { getWorkflowGraphInstance, listInstanceEvents } from '@/api/workflow-graph'\n",
    "import type { WorkflowRunEventItem } from '@/types/workflowVideo'\n",
]:
    script = script.replace(imp, "")

script = script.replace(
    "import { acceptTaskAssignment,\n  addTaskWatchers,\n  createTask,\n  createTaskComment,\n  delegateTaskAssignment,\n  getTaskStatsSummary,\n  getTaskWorkload,\n  listTaskActivity,\n  listTaskBoard,\n  listTaskGantt,\n  getTask,\n  listTasks,\n  listTaskWatchers,\n  rejectTaskAssignment,\n  reviewTaskDeliverable,\n  submitTaskDeliverable,\n  updateTaskStatus,\n} from '@/api/tasks'",
    "import {\n  createTask,\n  getTaskStatsSummary,\n  getTaskWorkload,\n  listTaskBoard,\n  listTaskGantt,\n  listTasks,\n} from '@/api/tasks'",
)

script = script.replace(
    "import { getErrorMessage } from '@/utils/errors'\nimport { formatDateTime } from '@/utils/formatters'\n",
    "import TaskDetailShell from '@/components/task-detail/TaskDetailShell.vue'\nimport {\n  resolveTaskUserFacingStateForTask,\n  TASK_USER_FACING_STATE_LABELS,\n  userFacingStateTagType,\n} from '@/domain/task-detail/user-state'\nimport { resolveTaskRunLabel } from '@/domain/task-detail/run-label'\nimport { getErrorMessage } from '@/utils/errors'\nimport { formatDateTime } from '@/utils/formatters'\n",
)

# Trim type imports
for unused in [
    "  TaskActivityEntry,\n",
    "  TaskWatcher,\n",
    "  WorkflowGraphInstanceDetail,\n",
    "  WorkflowNodeInstanceSummary,\n",
]:
    script = script.replace(unused, "")

# Remove detail refs block (from taskAttachmentUploading through commentFiles)
script = re.sub(
    r"const taskAttachmentUploading = ref\(false\).*?const commentFiles = ref<File\[\]>\(\[\]\)\n\n",
    "",
    script,
    count=1,
    flags=re.S,
)

script = re.sub(
    r"const delegateForm = reactive\(\{.*?\}\)\n\n",
    "",
    script,
    count=1,
    flags=re.S,
)

script = re.sub(
    r"const commentForm = reactive\(\{.*?\}\)\n\n",
    "",
    script,
    count=1,
    flags=re.S,
)

script = re.sub(
    r"const deliverableForm = reactive\(\{.*?\}\)\n\n",
    "",
    script,
    count=1,
    flags=re.S,
)

script = re.sub(
    r"const deliverableReviewForm = reactive\(\{.*?\}\)\n\n",
    "",
    script,
    count=1,
    flags=re.S,
)

# Remove dialog visibility refs for detail dialogs
for line in [
    "const commentSubmitting = ref(false)\n",
    "const deliverableSubmitting = ref(false)\n",
    "const statusSubmitting = ref(false)\n",
    "const approvalSubmitting = ref(false)\n",
    "const handshakeSubmitting = ref(false)\n",
    "const rejectCommentDialogVisible = ref(false)\n",
    "const rejectCommentText = ref('')\n",
    "const reworkDialogVisible = ref(false)\n",
    "const reworkCommentText = ref('')\n",
    "const handshakeRejectDialogVisible = ref(false)\n",
    "const handshakeRejectReason = ref('')\n",
    "const delegateDialogVisible = ref(false)\n",
    "const watcherSubmitting = ref(false)\n",
    "const watcherUserId = ref('')\n",
    "const selectedTaskFile = ref<File | null>(null)\n",
    "const taskAttachments = ref<Attachment[]>([])\n",
    "const taskActivity = ref<TaskActivityEntry[]>([])\n",
    "const taskWatchers = ref<TaskWatcher[]>([])\n",
    "const graphInstance = ref<WorkflowGraphInstanceDetail | null>(null)\n",
    "const workflowRunEvents = ref<WorkflowRunEventItem[]>([])\n",
]:
    script = script.replace(line, "")

script = script.replace("  Attachment,\n", "")

# Remove NEXT_STATUS_ACTIONS and STATUS constants used only in detail - keep for list columns
# Remove large computed block from selectedTask through showBatchRunDashboard
script = re.sub(
    r"const selectedTask = computed\(.*?\nconst videoProductionPanelRef = ref.*?\n",
    "",
    script,
    count=1,
    flags=re.S,
)

script = re.sub(
    r"const graphParentInstanceId = computed\(.*?\nconst EVENT_TYPE_LABELS:.*?\n\nfunction resolveRunEventLabel.*?\n\}\n\n",
    "",
    script,
    count=1,
    flags=re.S,
)

# Keep normalizeTagType, resolveDepartmentName, userEmailMap, departmentNameMap
# Remove delegateUserLabelMap and detail helpers
script = re.sub(
    r"const delegateUserLabelMap = computed\(.*?\n\nfunction resolveUserLabel.*?\n\}\n\nfunction resolveNodeEngineStateLabel.*?\n\}\n\nfunction resolveNodeEngineStateTagType.*?\n\}\n\nfunction formatNodeDuration.*?\n\}\n\n",
    "function resolveUserLabel(userId: string): string {\n  return userEmailMap.value.get(userId) ?? `用户 ${userId.slice(0, 8)}`\n}\n\n",
    script,
    count=1,
    flags=re.S,
)

script = re.sub(
    r"function resolveTaskListRunLabel\(task: Task\): string \{.*?\n\}\n\n",
    "function resolveTaskListRunLabel(task: Task): string {\n  const metadata = (task.extra_metadata as Record<string, unknown> | undefined) ?? {}\n  return resolveTaskRunLabel(task.title, metadata)\n}\n\n",
    script,
    count=1,
    flags=re.S,
)

script = re.sub(
    r"function resetCommentForm\(\): void \{.*?\}\n\n",
    "",
    script,
    count=1,
    flags=re.S,
)

script = re.sub(
    r"function resetDeliverableForm\(\): void \{.*?\}\n\n",
    "",
    script,
    count=1,
    flags=re.S,
)

script = re.sub(
    r"async function ensureTaskInList\(.*?\n\}\n\nasync function loadSelectedTaskDetails\(.*?\n\}\n\n",
    "",
    script,
    count=1,
    flags=re.S,
)

# Simplify loadData - remove detailOnly branch and loadSelectedTaskDetails calls
script = re.sub(
    r"async function loadData\(\): Promise<void> \{.*?finally \{\n    loading.value = false\n  \}\n\}",
    """async function loadData(): Promise<void> {
  loading.value = true

  try {
    const [taskList, boardColumns, ganttEntries, departmentList, summary, workload] = await Promise.all([
      listTasks(),
      listTaskBoard(),
      listTaskGantt(),
      listDepartments(),
      getTaskStatsSummary(),
      getTaskWorkload(),
    ])

    tasks.value = taskList
    taskBoard.value = boardColumns
    taskGantt.value = ganttEntries
    departments.value = departmentList
    statsSummary.value = summary
    workloadRows.value = workload

    if (authStore.isManagementRole) {
      users.value = await listUsers()
    } else if (authStore.user) {
      users.value = [authStore.user]
    }

    const preferredTaskId = props.initialSelectedTaskId?.trim()
    if (preferredTaskId && taskList.some((task) => task.id === preferredTaskId)) {
      selectedTaskId.value = preferredTaskId
    } else if (!taskList.some((task) => task.id === selectedTaskId.value)) {
      selectedTaskId.value = taskList[0]?.id ?? ''
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}""",
    script,
    count=1,
    flags=re.S,
)

# Remove all detail handler functions through watch on initialSelectedTaskId
script = re.sub(
    r"async function handleAddWatcher\(\): Promise<void> \{.*?async function handleDelegateAssignment\(\): Promise<void> \{.*?\n\}\n\n",
    "",
    script,
    count=1,
    flags=re.S,
)

script = script.replace(
    "function handleTaskClick(task: Task): void {\n  selectedTaskId.value = task.id\n  void loadSelectedTaskDetails(task.id)\n}",
    """function handleTaskClick(task: Task): void {
  selectedTaskId.value = task.id
}

function handleShellSelectTask(taskId: string): void {
  selectedTaskId.value = taskId
}

async function handleDetailActionDone(): Promise<void> {
  await loadData()
}""",
)

script = re.sub(
    r"watch\(\n  \(\) => props\.initialSelectedTaskId,.*?\n\)\n\nwatch\(\n  \(\) => tasks\.value,.*?\n\)",
    """watch(
  () => props.initialSelectedTaskId,
  (nextTaskId) => {
    if (!nextTaskId) {
      return
    }
    if (tasks.value.some((task) => task.id === nextTaskId)) {
      selectedTaskId.value = nextTaskId
    }
  },
)

watch(
  () => tasks.value,
  (taskList) => {
    const preferred = props.initialSelectedTaskId?.trim()
    if (!preferred || !taskList.some((task) => task.id === preferred)) {
      return
    }
    if (selectedTaskId.value === preferred) {
      return
    }
    selectedTaskId.value = preferred
  },
)""",
    script,
    count=1,
    flags=re.S,
)

# --- Template: replace detail column with TaskDetailShell ---
detail_col_start = template.find('<el-col :xs="24" :xl="props.detailOnly ? 24 : 12">')
detail_col_end = template.find("</el-col>", detail_col_start)
if detail_col_start < 0:
    raise SystemExit("Could not find detail column")

shell_col = """
      <el-col :xs="24" :xl="12">
        <TaskDetailShell
          :initial-selected-task-id="selectedTaskId || undefined"
          :delegate-user-options="props.delegateUserOptions"
          @select-task="handleShellSelectTask"
          @action-done="handleDetailActionDone"
        />
      </el-col>
"""

template = template[:detail_col_start] + shell_col + template[detail_col_end + len("</el-col>") :]

# Remove detailOnly conditionals from workspace col
template = template.replace('<el-col v-if="!props.detailOnly" :xs="24" :xl="12">', '<el-col :xs="24" :xl="12">')

# Remove detail dialogs from template (after workload card)
dialogs_start = template.find("<!-- 驳回审核对话框 -->")
if dialogs_start >= 0:
    template = template[:dialogs_start].rstrip() + "\n  </div>\n"

# --- Style: remove detail-only styles ---
for cls in [
    ".page__detail,\n",
    ".page__compact-meta",
    ".page__watchers",
    ".page__watcher-form",
    ".page__upload",
    ".page__upload-button",
    ".page__attachment",
    ".page__comments-collapse",
    ".page__timeline",
    ".page__node-",
    ".page__run-events",
    ".page__inline-tag",
    ".page__comment-",
]:
    pass  # keep style block mostly as-is for workspace

style = style.replace(".page__detail,\n", "")
style = re.sub(r"\.page__compact-meta \{.*?\}\n\n", "", style, flags=re.S)
style = re.sub(r"\.page__watchers \{.*?\}\n\n", "", style, flags=re.S)
style = re.sub(r"\.page__watcher-form \{.*?\}\n\n", "", style, flags=re.S)

out = f"""<script setup lang="ts">
{script.strip()}
</script>

<template>
{template.strip()}
</template>

<style scoped>
{style.strip()}
</style>
"""

TASKS_VIEW.write_text(out, encoding="utf-8")
print(f"Wrote {TASKS_VIEW} ({len(out.splitlines())} lines)")
