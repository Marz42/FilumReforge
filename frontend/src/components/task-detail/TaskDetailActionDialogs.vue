<script setup lang="ts">
import type { TaskCenterUserOption } from '@/types/api'

const rejectCommentDialogVisible = defineModel<boolean>('rejectCommentDialogVisible', { required: true })
const rejectCommentText = defineModel<string>('rejectCommentText', { required: true })
const reworkDialogVisible = defineModel<boolean>('reworkDialogVisible', { required: true })
const reworkCommentText = defineModel<string>('reworkCommentText', { required: true })
const handshakeRejectDialogVisible = defineModel<boolean>('handshakeRejectDialogVisible', { required: true })
const handshakeRejectReason = defineModel<string>('handshakeRejectReason', { required: true })
const delegateDialogVisible = defineModel<boolean>('delegateDialogVisible', { required: true })
const delegateAssigneeId = defineModel<string>('delegateAssigneeId', { required: true })
const delegateReason = defineModel<string>('delegateReason', { required: true })

defineProps<{
  approvalSubmitting: boolean
  handshakeSubmitting: boolean
  delegateCandidateOptions: TaskCenterUserOption[]
}>()

const emit = defineEmits<{
  confirmReject: []
  confirmRework: []
  confirmHandshakeReject: []
  confirmDelegate: []
}>()
</script>

<template>
  <el-dialog v-model="rejectCommentDialogVisible" title="驳回说明" width="480px">
    <el-form label-position="top">
      <el-form-item label="驳回原因（可选）">
        <el-input
          v-model="rejectCommentText"
          type="textarea"
          :rows="3"
          placeholder="说明本次驳回的原因，便于执行人修改"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="rejectCommentDialogVisible = false">取消</el-button>
      <el-button type="danger" :loading="approvalSubmitting" @click="emit('confirmReject')">
        确认驳回
      </el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="reworkDialogVisible" title="返工说明" width="480px">
    <el-form label-position="top">
      <el-form-item label="返工原因（必填）">
        <el-input
          v-model="reworkCommentText"
          type="textarea"
          :rows="3"
          placeholder="请填写需要补充或修改的内容"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="reworkDialogVisible = false">取消</el-button>
      <el-button type="danger" :loading="approvalSubmitting" @click="emit('confirmRework')">
        确认打回
      </el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="handshakeRejectDialogVisible" title="退回协商" width="480px">
    <el-form label-position="top">
      <el-form-item label="协商原因（必填）">
        <el-input
          v-model="handshakeRejectReason"
          type="textarea"
          :rows="3"
          placeholder="请说明当前不能接单的原因，便于发起人调整"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handshakeRejectDialogVisible = false">取消</el-button>
      <el-button type="danger" :loading="handshakeSubmitting" @click="emit('confirmHandshakeReject')">
        确认退回
      </el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="delegateDialogVisible" title="转办任务" width="520px">
    <el-form label-position="top">
      <el-form-item label="转办给">
        <el-select v-model="delegateAssigneeId" placeholder="请选择转办目标">
          <el-option
            v-for="option in delegateCandidateOptions"
            :key="option.user_id"
            :label="option.label"
            :value="option.user_id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="转办原因（必填）">
        <el-input
          v-model="delegateReason"
          type="textarea"
          :rows="3"
          placeholder="说明转办原因，便于新执行人理解背景"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="delegateDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="handshakeSubmitting" @click="emit('confirmDelegate')">
        确认转办
      </el-button>
    </template>
  </el-dialog>
</template>
