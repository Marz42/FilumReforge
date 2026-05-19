<script setup lang="ts">
import type { DepartmentTreeNode } from '@/types/api'

interface Props {
  tree: DepartmentTreeNode[]
  selectedDepartmentId: string
  loading?: boolean
}

withDefaults(defineProps<Props>(), {
  loading: false,
})

const emit = defineEmits<{
  select: [departmentId: string]
  'create-root': []
  'create-child': [parentId: string]
}>()

const treeProps = {
  label: 'name',
  children: 'children',
}

function handleNodeClick(node: DepartmentTreeNode): void {
  emit('select', node.id)
}

function handleCreateChild(parentId: string): void {
  emit('create-child', parentId)
}
</script>

<template>
  <el-card shadow="never" class="department-tree-panel" v-loading="loading" data-testid="departments-tree">
    <template #header>
      <div class="department-tree-panel__header">
        <span>组织树</span>
        <el-button size="small" data-testid="departments-create-root" @click="emit('create-root')">
          新建根部门
        </el-button>
      </div>
    </template>

    <el-tree
      :data="tree"
      :props="treeProps"
      node-key="id"
      highlight-current
      :current-node-key="selectedDepartmentId || undefined"
      default-expand-all
      empty-text="暂无部门数据"
      @node-click="handleNodeClick"
    >
      <template #default="{ data }: { data: DepartmentTreeNode }">
        <div class="department-tree-panel__node">
          <span>{{ data.name }}</span>
          <el-button
            link
            type="primary"
            size="small"
            data-testid="departments-create-child"
            @click.stop="handleCreateChild(data.id)"
          >
            子部门
          </el-button>
        </div>
      </template>
    </el-tree>
  </el-card>
</template>

<style scoped>
.department-tree-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.department-tree-panel__node {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding-right: 8px;
}
</style>
