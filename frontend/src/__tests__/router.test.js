/**
 * Tests for Vue Router configuration.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock matchMedia before any import
vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({
  matches: false,
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
}))

describe('Router', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('exports a router instance', async () => {
    const { default: router } = await import('../router')
    expect(router).toBeTruthy()
    expect(router.getRoutes).toBeDefined()
  })

  it('has all required routes', async () => {
    const { default: router } = await import('../router')
    const routes = router.getRoutes()
    const routeNames = routes.map(r => r.name).filter(Boolean)

    expect(routeNames).toContain('Home')
    expect(routeNames).toContain('Login')
    expect(routeNames).toContain('Projects')
    expect(routeNames).toContain('Profile')
    expect(routeNames).toContain('Datasets')
    expect(routeNames).toContain('Admin')
  })

  it('Login route has guest meta', async () => {
    const { default: router } = await import('../router')
    const loginRoute = router.getRoutes().find(r => r.name === 'Login')
    expect(loginRoute.meta.guest).toBe(true)
  })

  it('Admin route has requiresAdmin meta', async () => {
    const { default: router } = await import('../router')
    const adminRoute = router.getRoutes().find(r => r.name === 'Admin')
    expect(adminRoute.meta.requiresAdmin).toBe(true)
  })

  it('has project dashboard route with children', async () => {
    const { default: router } = await import('../router')
    const routes = router.getRoutes()
    const projectRouteNames = routes.map(r => r.name).filter(Boolean)

    expect(projectRouteNames).toContain('ProjectData')
    expect(projectRouteNames).toContain('ProjectParameters')
    expect(projectRouteNames).toContain('ProjectResults')
  })
})
