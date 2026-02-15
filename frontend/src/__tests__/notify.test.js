/**
 * Tests for browser notification utility.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { isSupported, requestPermission, notify, notifyJobCompleted, notifyJobFailed } from '../utils/notify'

describe('notify utility', () => {
  beforeEach(() => {
    localStorage.clear()
    // Reset Notification mock
    vi.stubGlobal('Notification', class MockNotification {
      static permission = 'default'
      static requestPermission = vi.fn().mockResolvedValue('granted')
      constructor(title, options) {
        this.title = title
        this.options = options
        this.close = vi.fn()
      }
    })
  })

  describe('isSupported', () => {
    it('returns true when Notification is available', () => {
      expect(isSupported()).toBe(true)
    })

    it('checks window.Notification', () => {
      // isSupported reads window.Notification at call time
      // In the test env we've stubbed it, so it should be truthy
      expect(isSupported()).toBe(true)
    })
  })

  describe('requestPermission', () => {
    it('returns true when already granted', async () => {
      Notification.permission = 'granted'
      expect(await requestPermission()).toBe(true)
    })

    it('returns false when already denied', async () => {
      Notification.permission = 'denied'
      expect(await requestPermission()).toBe(false)
    })

    it('returns false when user opted out via localStorage', async () => {
      localStorage.setItem('predomics_notifications', 'denied')
      expect(await requestPermission()).toBe(false)
    })

    it('requests permission when status is default', async () => {
      Notification.permission = 'default'
      Notification.requestPermission = vi.fn().mockResolvedValue('granted')
      const result = await requestPermission()
      expect(Notification.requestPermission).toHaveBeenCalled()
      expect(result).toBe(true)
    })

    it('stores denial in localStorage', async () => {
      Notification.permission = 'default'
      Notification.requestPermission = vi.fn().mockResolvedValue('denied')
      await requestPermission()
      expect(localStorage.getItem('predomics_notifications')).toBe('denied')
    })
  })

  describe('notify', () => {
    it('returns null when not granted', () => {
      Notification.permission = 'default'
      expect(notify('Title', 'Body')).toBeNull()
    })

    it('creates notification when granted', () => {
      Notification.permission = 'granted'
      const n = notify('Test Title', 'Test Body')
      expect(n).toBeTruthy()
      expect(n.title).toBe('Test Title')
    })

    it('sets onclick handler when provided', () => {
      Notification.permission = 'granted'
      const onClick = vi.fn()
      const n = notify('Title', 'Body', { onClick })
      expect(n.onclick).toBeDefined()
    })
  })

  describe('notifyJobCompleted', () => {
    it('includes AUC in notification body', () => {
      Notification.permission = 'granted'
      const n = notifyJobCompleted('My Project', { auc: 0.9234, k: 5, jobId: 'j1' })
      expect(n).toBeTruthy()
      expect(n.options.body).toContain('0.9234')
      expect(n.options.body).toContain('k=5')
    })

    it('works without AUC', () => {
      Notification.permission = 'granted'
      const n = notifyJobCompleted('My Project')
      expect(n.options.body).toContain('My Project')
    })
  })

  describe('notifyJobFailed', () => {
    it('includes project name in failure notification', () => {
      Notification.permission = 'granted'
      const n = notifyJobFailed('My Project', { jobId: 'j1' })
      expect(n).toBeTruthy()
      expect(n.options.body).toContain('My Project')
      expect(n.options.body).toContain('failed')
    })
  })
})
