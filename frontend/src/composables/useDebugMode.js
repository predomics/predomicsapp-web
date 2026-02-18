import { ref, watchEffect } from 'vue'

const debugMode = ref(localStorage.getItem('debugMode') === 'true')

watchEffect(() => {
  localStorage.setItem('debugMode', debugMode.value ? 'true' : 'false')
})

export function useDebugMode() {
  function toggle() {
    debugMode.value = !debugMode.value
  }
  return { debugMode, toggle }
}
