"""Generate TaskDetailShell.vue from TasksView.vue detail sections."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS_VIEW = ROOT / "src/views/TasksView.vue"
SHELL_OUT = ROOT / "src/components/task-detail/TaskDetailShell.vue"

content = TASKS_VIEW.read_text(encoding="utf-8")
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

# --- script transforms ---
script = script.replace(
    "import { acceptTaskAssignment,\n  addTaskWatchers,\n  createTask,\n  createTaskComment,\n  delegateTaskAssignment,\n  getTaskStatsSummary,\n  getTaskWorkload,\n  listTaskActivity,\n  listTaskBoard,\n  listTaskGantt,\n  getTask,\n  listTasks,\n  listTaskWatchers,",
    "import { acceptTaskAssignment,\n  addTaskWatchers,\n  createTaskComment,\n  delegateTaskAssignment,\n  listTaskActivity,\n  getTask,\n  listTaskWatchers,",
)
script = script.replace("import { listDepartments } from '@/api/departments'\n", "")
script = script.replace(
    "import FilumDateTimePicker from '@/components/common/FilumDateTimePicker.vue'\n",
    "",
)
script = script.replace(
    "import { TASK_CENTER_V2_UI_ENABLED } from '@/constants/task-center'\n",
    "import { TASK_CENTER_V2_UI_ENABLED } from '@/constants/task-center'\n",
)
if "TASK_CENTER_V2_UI_ENABLED" not in script:
    script = script.replace(
        "import { ATTACHMENT_ACCEPT, validateAttachmentFile } from '@/constants/attachments'\n",
        "import { ATTACHMENT_ACCEPT, validateAttachmentFile } from '@/constants/attachments'\n"
        "import { TASK_CENTER_V2_UI_ENABLED } from '@/constants/task-center'\n",
    )

script = re.sub(
    r"interface Props \{.*?\}",
    """interface Props {
  initialSelectedTaskId?: string
  delegateUserOptions?: TaskCenterUserOption[]
  emptyDescription?: string
}""",
    script,
    count=1,
    flags=re.S,
)

script = re.sub(
    r"const props = withDefaults\(defineProps<Props>\(\), \{.*?\}\)",
    """const props = withDefaults(defineProps<Props>(), {
  delegateUserOptions: () => [],
  emptyDescription: '请从左侧选择任务',
})

const emit = defineEmits<{
  actionDone: []
  selectTask: [taskId: string]
}>()""",
    script,
    count=1,
    flags=re.S,
)

# Remove workspace-only refs
for line in [
    "const submitting = ref(false)\n",
    "const dialogVisible = ref(false)\n",
    "const tasks = ref<Task[]>([])\n",
    "const taskBoard = ref<TaskBoardColumn[]>([])\n",
    "const taskGantt = ref<TaskGanttEntry[]>([])\n",
    "const statsSummary = ref<TaskStatsSummary | null>(null)\n",
    "const workloadRows = ref<TaskWorkloadRow[]>([])\n",
    "const selectedTaskId = ref('')\n",
    "const viewMode = ref<'list' | 'board' | 'gantt'>('list')\n",
]:
    script = script.replace(line, "")

script = script.replace(
    "const loading = ref(false)\n",
    "const loading = ref(false)\nconst task = ref<Task | null>(null)\n",
)

script = script.replace(
    "const delegateForm = reactive({\n  assignee_id: '',\n  reason: '',\n})\n\nconst form = reactive({\n  title: '',\n  description: '',\n  assignee_id: '',\n  department_id: '',\n  priority: 'medium' as TaskPriority,\n  due_date: null as Date | null,\n})\n\nconst commentForm",
    "const delegateForm = reactive({\n  assignee_id: '',\n  reason: '',\n})\n\nconst commentForm",
)

script = script.replace(
    "const selectedTask = computed(() => tasks.value.find((task) => task.id === selectedTaskId.value) ?? null)",
    "const selectedTask = computed(() => task.value)",
)

script = script.replace(
    "const completionRateText = computed(() => formatRate(statsSummary.value?.completion_rate ?? 0))\nconst overdueRateText = computed(() => formatRate(statsSummary.value?.overdue_rate ?? 0))\n",
    "",
)

script = script.replace(
    "const showBatchRunDashboard = computed(() => isGraphRootBatchTask.value && graphInstance.value !== null)",
    "const showBatchRunDashboard = computed(\n  () =>\n    !TASK_CENTER_V2_UI_ENABLED\n    && isGraphRootBatchTask.value\n    && graphInstance.value !== null,\n)",
)

script = script.replace(
    "const assigneeOptions = computed(() => {\n  if (authStore.isManagementRole) {\n    return users.value.filter((user) => user.status === 'active')\n  }\n\n  return authStore.user ? [authStore.user] : []\n})\n",
    "",
)

script = re.sub(
    r"function resetTaskForm\(\): void \{.*?\}\n\n",
    "",
    script,
    count=1,
    flags=re.S,
)

script = re.sub(
    r"function formatRate\(value: number\): string \{.*?\}\n\n",
    "",
    script,
    count=1,
    flags=re.S,
)

script = script.replace(
    """async function ensureTaskInList(taskId: string): Promise<void> {
  if (tasks.value.some((task) => task.id === taskId)) {
    return
  }
  try {
    const task = await getTask(taskId)
    tasks.value = [task, ...tasks.value.filter((item) => item.id !== task.id)]
  } catch {
    // ignore — detail loaders will surface errors
  }
}""",
    """async function refreshTaskRecord(taskId: string): Promise<void> {
  try {
    task.value = await getTask(taskId)
  } catch {
    // ignore — detail loaders will surface errors
  }
}""",
)

script = script.replace(
    "  await ensureTaskInList(taskId)\n  const [attachments, activity, watchers] = await Promise.all([",
    "  await refreshTaskRecord(taskId)\n  const [attachments, activity, watchers] = await Promise.all([",
)

script = script.replace(
    "  const metadata = (tasks.value.find((t) => t.id === taskId)?.extra_metadata ?? {}) as Record<string, unknown>",
    "  const metadata = (task.value?.extra_metadata ?? {}) as Record<string, unknown>",
)

script = re.sub(
    r"async function loadData\(\): Promise<void> \{.*?\n\}\n\nasync function handleAddWatcher",
    """async function loadUsers(): Promise<void> {
  if (authStore.isManagementRole) {
    users.value = await listUsers()
  } else if (authStore.user) {
    users.value = [authStore.user]
  }
}

async function loadDepartmentsIfNeeded(): Promise<void> {
  if (departments.value.length > 0) {
    return
  }
  try {
    const { listDepartments } = await import('@/api/departments')
    departments.value = await listDepartments()
  } catch {
    departments.value = []
  }
}

async function initialize(): Promise<void> {
  loading.value = true
  try {
    await Promise.all([loadUsers(), loadDepartmentsIfNeeded()])
    const preferredTaskId = props.initialSelectedTaskId?.trim()
    if (preferredTaskId) {
      await loadSelectedTaskDetails(preferredTaskId)
    } else {
      task.value = null
      taskAttachments.value = []
      taskActivity.value = []
      taskWatchers.value = []
      graphInstance.value = null
      workflowRunEvents.value = []
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function reloadAfterAction(): Promise<void> {
  if (!selectedTask.value) {
    emit('actionDone')
    return
  }
  await loadSelectedTaskDetails(selectedTask.value.id)
  emit('actionDone')
}

async function handleAddWatcher""",
    script,
    count=1,
    flags=re.S,
)

# Replace loadData() calls in handlers
script = script.replace("await loadData()", "await reloadAfterAction()")

script = re.sub(
    r"async function handleCreateTask\(\): Promise<void> \{.*?\n\}\n\nfunction handleTaskClick",
    "function handleTaskClick",
    script,
    count=1,
    flags=re.S,
)

script = script.replace(
    """function handleTaskClick(task: Task): void {
  selectedTaskId.value = task.id
  void loadSelectedTaskDetails(task.id)
}""",
    "",
)

script = script.replace(
    "onMounted(() => {\n  resetTaskForm()\n  void loadData()\n})",
    "onMounted(() => {\n  void initialize()\n})",
)

script = re.sub(
    r"watch\(\n  \(\) => props\.externalViewMode,.*?\n\)\n\n",
    "",
    script,
    count=1,
    flags=re.S,
)

script = re.sub(
    r"watch\(\n  \(\) => props\.initialSelectedTaskId,.*?\n\)\n\nwatch\(\n  \(\) => tasks\.value,.*?\n\)",
    """watch(
  () => props.initialSelectedTaskId,
  async (nextTaskId) => {
    if (!nextTaskId) {
      task.value = null
      taskAttachments.value = []
      taskActivity.value = []
      taskWatchers.value = []
      graphInstance.value = null
      workflowRunEvents.value = []
      return
    }
    await loadSelectedTaskDetails(nextTaskId)
  },
)""",
    script,
    count=1,
    flags=re.S,
)

# Clean unused type imports
for unused in [
    "  TaskBoardColumn,\n",
    "  TaskGanttEntry,\n",
    "  TaskStatsSummary,\n",
    "  TaskWorkloadRow,\n",
]:
    script = script.replace(unused, "")

# --- template: extract detail card + dialogs ---
detail_start = template.find('<el-card shadow="never" class="page__detail"')
detail_end = template.find("</el-col>", detail_start)
if detail_start < 0 or detail_end < 0:
    raise SystemExit("Could not locate detail card in template")

detail_block = template[detail_start:detail_end]
detail_block = detail_block.replace("props.detailOnly && !selectedTask", "!selectedTask")
detail_block = detail_block.replace(
    'description="请从左侧选择任务"',
    ':description="props.emptyDescription"',
)
detail_block = detail_block.replace(
    "@open-task=\"(taskId) => { selectedTaskId = taskId; void loadSelectedTaskDetails(taskId) }\"",
    '@select-task="(taskId: string) => emit(\'selectTask\', taskId)"',
)
detail_block = detail_block.replace(
    "@action-done=\"() => selectedTask && loadSelectedTaskDetails(selectedTask.id)\"",
    "@action-done=\"reloadAfterAction\"",
)
detail_block = re.sub(
    r"@submitted=\"\(\) => selectedTask && loadSelectedTaskDetails\(selectedTask\.id\)\"",
    '@submitted="reloadAfterAction"',
    detail_block,
)
detail_block = re.sub(
    r"@dispatched=\"\(\) => selectedTask && loadSelectedTaskDetails\(selectedTask\.id\)\"",
    '@dispatched="reloadAfterAction"',
    detail_block,
)
detail_block = re.sub(
    r"@rejected=\"\(\) => selectedTask && loadSelectedTaskDetails\(selectedTask\.id\)\"",
    '@rejected="reloadAfterAction"',
    detail_block,
)
detail_block = re.sub(
    r"@finalized=\"\(\) => selectedTask && loadSelectedTaskDetails\(selectedTask\.id\)\"",
    '@finalized="reloadAfterAction"',
    detail_block,
)

dialogs_start = template.find("<!-- 驳回审核对话框 -->")
dialogs_block = template[dialogs_start:]
dialogs_block = re.sub(
    r"<el-dialog\s+v-if=\"props\.showCreateTaskComposer\".*?</el-dialog>\n\n",
    "",
    dialogs_block,
    count=1,
    flags=re.S,
)

shell_template = f"""<template>
  <div class="task-detail-shell" data-testid="tasks-detail-panel">
    {detail_block.strip()}

    {dialogs_block.strip()}
  </div>
</template>
"""

# Fix BatchRunDashboard event name
shell_template = shell_template.replace("@select-task=", "@open-task=")

# --- style: detail-related only ---
shell_style = """
.task-detail-shell {
  min-height: 100%;
}

.page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page__detail {
  min-height: 100%;
}

.page__compact-meta {
  margin-bottom: 16px;
}

.page__watchers {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.page__watcher-form {
  display: flex;
  gap: 12px;
}

.page__upload {
  margin-bottom: 12px;
}

.page__upload-button {
  margin-bottom: 16px;
}

.page__attachment-card {
  margin-bottom: 8px;
}

.page__attachment-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page__comments-collapse {
  margin-top: 16px;
}

.page__timeline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.page__timeline-text {
  margin: 0;
  color: #606266;
}

.page__inline-tag {
  margin-left: 8px;
}

.page__comment-attachments {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.page__comment-attachment-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.page__node-timeline {
  width: 100%;
}

.page__node-card {
  margin-bottom: 8px;
}

.page__node-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.page__node-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page__node-meta {
  margin: 4px 0 0;
  color: #909399;
  font-size: 13px;
}

.page__node-meta--terminated {
  color: #f56c6c;
}

.page__run-events {
  margin-top: 16px;
}
"""

shell_content = f"""<script setup lang="ts">
{script.strip()}
</script>

{shell_template}

<style scoped>
{shell_style.strip()}
</style>
"""

SHELL_OUT.write_text(shell_content, encoding="utf-8")
print(f"Wrote {SHELL_OUT} ({len(shell_content.splitlines())} lines)")
