import { getCurrentScope, onScopeDispose } from 'vue'
import { getSessionEpoch, isCurrentSession, onSessionChange } from '@/api/session'

/** Own a single replaceable read. Session changes and disposal invalidate even uncancellable mocks. */
export function useLatestRequest(onInvalidate: () => void = () => {}) {
  let generation = 0
  let controller: AbortController | undefined
  let disposed = false
  function invalidate() {
    generation += 1
    controller?.abort()
    controller = undefined
    onInvalidate()
  }
  const unsubscribe = onSessionChange(invalidate)
  function dispose() {
    disposed = true
    unsubscribe()
    invalidate()
  }
  if (getCurrentScope()) onScopeDispose(dispose)
  return {
    invalidate,
    dispose,
    start() {
      generation += 1
      controller?.abort()
      controller = new AbortController()
      if (disposed) controller.abort()
      const signal = controller.signal
      const request = generation
      const epoch = getSessionEpoch()
      return { signal, isCurrent: () => !disposed && !signal.aborted && generation === request && isCurrentSession(epoch) }
    },
  }
}
