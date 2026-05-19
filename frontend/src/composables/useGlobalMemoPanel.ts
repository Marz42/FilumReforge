import { ref } from 'vue'

const panelVisible = ref(false)

export function useGlobalMemoPanel() {
  function openPanel(): void {
    panelVisible.value = true
  }

  function closePanel(): void {
    panelVisible.value = false
  }

  function togglePanel(): void {
    panelVisible.value = !panelVisible.value
  }

  return {
    panelVisible,
    openPanel,
    closePanel,
    togglePanel,
  }
}
