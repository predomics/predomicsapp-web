<template>
  <Teleport to="body">
    <div class="toast-container" v-if="toasts.length > 0">
      <transition-group name="toast">
        <div
          v-for="t in toasts"
          :key="t.id"
          :class="['toast', t.type]"
          @click="removeToast(t.id)"
        >
          <span class="toast-icon">{{ icon(t.type) }}</span>
          <span class="toast-msg">{{ t.message }}</span>
          <button class="toast-close">&times;</button>
        </div>
      </transition-group>
    </div>
  </Teleport>
</template>

<script setup>
import { useToast } from '../composables/useToast'
const { toasts, removeToast } = useToast()

function icon(type) {
  const icons = { success: '\u2713', error: '\u2717', warning: '\u26A0', info: '\u2139' }
  return icons[type] || icons.info
}
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-width: 380px;
}

.toast {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 0.8rem;
  border-radius: 8px;
  font-size: 0.85rem;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transition: all 0.3s ease;
}

.toast.success { background: #e8f5e9; color: #2e7d32; border-left: 3px solid #4caf50; }
.toast.error   { background: #ffebee; color: #c62828; border-left: 3px solid #f44336; }
.toast.warning { background: #fff3e0; color: #e65100; border-left: 3px solid #ff9800; }
.toast.info    { background: #e3f2fd; color: #1565c0; border-left: 3px solid #2196f3; }

.toast-icon { font-size: 1rem; flex-shrink: 0; }
.toast-msg { flex: 1; line-height: 1.3; }
.toast-close {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  color: inherit;
  opacity: 0.5;
  padding: 0;
  line-height: 1;
}
.toast-close:hover { opacity: 1; }

/* Transition animations */
.toast-enter-active { animation: slideIn 0.3s ease; }
.toast-leave-active { animation: slideOut 0.2s ease; }

@keyframes slideIn {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
@keyframes slideOut {
  from { transform: translateX(0); opacity: 1; }
  to { transform: translateX(100%); opacity: 0; }
}
</style>
