import { defineStore } from 'pinia'
import { ref, computed, watchEffect } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const mode = ref(localStorage.getItem('theme') || 'system')

  const systemDark = ref(
    window.matchMedia('(prefers-color-scheme: dark)').matches
  )

  // Listen for system preference changes
  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  mq.addEventListener('change', (e) => {
    systemDark.value = e.matches
  })

  const isDark = computed(() => {
    if (mode.value === 'dark') return true
    if (mode.value === 'light') return false
    return systemDark.value
  })

  function setMode(m) {
    mode.value = m
    localStorage.setItem('theme', m)
  }

  function cycle() {
    const order = ['light', 'dark', 'system']
    const idx = order.indexOf(mode.value)
    setMode(order[(idx + 1) % order.length])
  }

  // Apply class on <html>
  watchEffect(() => {
    document.documentElement.classList.toggle('dark', isDark.value)
    document.documentElement.classList.toggle('light', !isDark.value)
  })

  return { mode, isDark, setMode, cycle }
})
