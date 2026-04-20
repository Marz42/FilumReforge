<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

import { routeAICommand } from '@/api/ai'
import type { AIRouterResult } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

const dialogVisible = ref(false)
const loading = ref(false)
const inputText = ref('')
const result = ref<AIRouterResult | null>(null)

function openDialog(nextValue?: string): void {
  if (nextValue) {
    inputText.value = nextValue
  }
  dialogVisible.value = true
}

async function handleSubmit(): Promise<void> {
  const normalizedText = inputText.value.trim()
  if (!normalizedText) {
    ElMessage.warning('请输入 @系统 或 / 命令')
    return
  }

  loading.value = true
  try {
    result.value = await routeAICommand(normalizedText)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

defineExpose({
  openDialog,
  handleSubmit,
  inputText,
  result,
})
</script>

<template>
  <div class="command-bar">
    <el-button plain @click="openDialog()">AI 命令</el-button>

    <el-dialog v-model="dialogVisible" title="系统命令与 AI Router" width="720px">
      <div class="command-bar__quick-actions">
        <el-button size="small" @click="inputText = '/profile'">/profile</el-button>
        <el-button size="small" @click="inputText = '/tasks'">/tasks</el-button>
        <el-button size="small" @click="inputText = '/messages unread'">/messages unread</el-button>
        <el-button size="small" @click="inputText = '@系统 入职流程是什么？'">
          @系统 入职流程是什么？
        </el-button>
      </div>

      <el-input
        v-model="inputText"
        id="command-bar-input"
        type="textarea"
        :rows="4"
        resize="none"
        placeholder="输入 @系统 问题，或使用 /profile /tasks /messages /docs 等命令"
      />

      <div class="command-bar__actions">
        <el-button data-testid="command-bar-submit" type="primary" :loading="loading" @click="handleSubmit">
          执行
        </el-button>
      </div>

      <el-empty v-if="!result" description="命令结果会显示在这里" />

      <el-card v-else shadow="never" class="command-bar__result">
        <template #header>
          <div class="command-bar__result-header">
            <span>{{ result.mode === 'mention' ? '@系统' : `/${result.command_name ?? 'command'}` }}</span>
            <el-tag size="small" effect="plain">
              {{ result.tool_results.length }} 个工具结果
            </el-tag>
          </div>
        </template>

        <pre class="command-bar__reply">{{ result.reply_text }}</pre>

        <el-table
          v-if="result.knowledge_hits.length > 0"
          :data="result.knowledge_hits"
          size="small"
          border
        >
          <el-table-column prop="title" label="知识命中" min-width="160" />
          <el-table-column prop="slug" label="Slug" min-width="150" />
          <el-table-column prop="score" label="相关度" width="100" />
        </el-table>
      </el-card>
    </el-dialog>
  </div>
</template>

<style scoped>
.command-bar {
  display: flex;
  align-items: center;
}

.command-bar__quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.command-bar__actions {
  display: flex;
  justify-content: flex-end;
  margin: 12px 0 20px;
}

.command-bar__result {
  margin-top: 12px;
}

.command-bar__result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.command-bar__reply {
  margin: 0 0 16px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
}
</style>
