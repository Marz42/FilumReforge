<script setup lang="ts">
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

const architectureHighlights = [
  '模块化单体',
  '任务绑定沟通留痕',
  'Redis 异步通知总线',
  '官方 openai SDK + Tool Calling',
]

const phaseAChecklist = [
  '标准化 memory-bank 文档入口',
  '建立前端与后端工程骨架',
  '补齐基础容器编排与验证基线',
]
</script>

<template>
  <el-container class="layout">
    <el-header class="layout__header">
      <div>
        <h1 class="layout__title">{{ appStore.projectName }}</h1>
        <p class="layout__subtitle">企业内部管理平台基础工程骨架</p>
      </div>
      <el-tag type="primary" effect="dark">{{ appStore.currentPhase }}</el-tag>
    </el-header>

    <el-main class="layout__main">
      <el-row :gutter="20">
        <el-col :xs="24" :lg="16">
          <el-card shadow="never">
            <template #header>
              <span>{{ appStore.headerTitle }}</span>
            </template>

            <el-alert
              title="阶段 A 已进入工程初始化"
              type="success"
              :closable="false"
              show-icon
            />

            <el-descriptions :column="1" border class="section">
              <el-descriptions-item label="当前状态">
                {{ appStore.deliveryStatus }}
              </el-descriptions-item>
              <el-descriptions-item label="前端基线">
                Vue 3、TypeScript、Vite、Pinia、Vue Router、Element Plus、Axios
              </el-descriptions-item>
              <el-descriptions-item label="协作约束">
                任务沟通必须绑定 Task，上层能力以统一抽象接入。
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>

        <el-col :xs="24" :lg="8">
          <el-card shadow="never" class="section-card">
            <template #header>
              <span>架构重点</span>
            </template>

            <el-space wrap>
              <el-tag
                v-for="item in architectureHighlights"
                :key="item"
                type="info"
                effect="plain"
              >
                {{ item }}
              </el-tag>
            </el-space>
          </el-card>

          <el-card shadow="never" class="section-card">
            <template #header>
              <span>阶段 A 清单</span>
            </template>

            <el-timeline>
              <el-timeline-item
                v-for="item in phaseAChecklist"
                :key="item"
                type="primary"
                hollow
              >
                {{ item }}
              </el-timeline-item>
            </el-timeline>
          </el-card>
        </el-col>
      </el-row>
    </el-main>
  </el-container>
</template>

<style scoped>
.layout {
  min-height: 100vh;
  background: #f5f7fa;
}

.layout__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 32px;
  background: #1f2d3d;
  color: #fff;
}

.layout__title {
  margin: 0;
  font-size: 28px;
}

.layout__subtitle {
  margin: 8px 0 0;
  color: #d3dce6;
}

.layout__main {
  padding: 24px;
}

.section {
  margin-top: 20px;
}

.section-card {
  margin-bottom: 20px;
}
</style>
