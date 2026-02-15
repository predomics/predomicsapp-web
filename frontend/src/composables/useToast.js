/**
 * Toast notification composable — global reactive toast queue.
 *
 * Usage:
 *   import { useToast } from '../composables/useToast'
 *   const { addToast } = useToast()
 *   addToast('Something happened', 'success')   // success | error | warning | info
 */
import { reactive } from 'vue'

const toasts = reactive([])
let _nextId = 0

function addToast(message, type = 'info', duration = 5000) {
  const id = _nextId++
  toasts.push({ id, message, type })
  if (duration > 0) {
    setTimeout(() => removeToast(id), duration)
  }
}

function removeToast(id) {
  const idx = toasts.findIndex(t => t.id === id)
  if (idx >= 0) toasts.splice(idx, 1)
}

export function useToast() {
  return { toasts, addToast, removeToast }
}
