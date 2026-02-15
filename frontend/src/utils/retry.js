/**
 * Retry wrapper for API calls with exponential backoff.
 *
 * Usage:
 *   import { withRetry } from '../utils/retry'
 *   const { data } = await withRetry(() => axios.get('/api/...'), { retries: 3 })
 */
export async function withRetry(fn, { retries = 3, delay = 1000 } = {}) {
  for (let i = 0; i <= retries; i++) {
    try {
      return await fn()
    } catch (error) {
      if (i === retries) throw error
      // Don't retry client errors (4xx)
      if (error.response?.status >= 400 && error.response?.status < 500) throw error
      await new Promise(r => setTimeout(r, delay * (i + 1)))
    }
  }
}
