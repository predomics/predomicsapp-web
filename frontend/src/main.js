import { createApp } from 'vue'
import { createPinia } from 'pinia'
import axios from 'axios'
import App from './App.vue'
import router from './router'
import i18n from './i18n'
import { useToast } from './composables/useToast'

const app = createApp(App)
app.use(createPinia())
app.use(i18n)
app.use(router)

// Global Axios error interceptor — show toast for server errors
const { addToast } = useToast()
axios.interceptors.response.use(
  response => response,
  error => {
    const status = error.response?.status
    // Skip 401 (handled by auth store) and cancelled requests
    if (status !== 401 && !axios.isCancel(error)) {
      const msg = status === 429
        ? 'Too many requests — please slow down'
        : (error.response?.data?.error?.message
          || error.response?.data?.detail
          || error.message
          || 'Network error')
      addToast(msg, status === 429 ? 'warning' : (status >= 500 ? 'error' : 'warning'))
    }
    return Promise.reject(error)
  },
)

app.mount('#app')
