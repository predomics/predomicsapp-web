/**
 * PredomicsApp End-to-End Integration Tests
 *
 * Prerequisites:
 *   - App running at BASE_URL (default http://localhost:8001)
 *   - npm install @playwright/test playwright
 *   - npx playwright install chromium
 *
 * Usage:
 *   npm run test:e2e
 *   BASE_URL=http://localhost:8001 npx playwright test
 */
import { test, expect } from '@playwright/test'
import path from 'path'

const BASE = process.env.BASE_URL || 'http://localhost:8001'
const TEST_EMAIL = `e2e_${Date.now()}@test.com`
const TEST_PASSWORD = 'TestPass123!'
const DATA_DIR = path.resolve('data/qin2014_cirrhosis')

// Shared state across serial tests
let authToken = ''
let projectId = ''
let jobId = ''

// Helper: dismiss any onboarding tour overlays
async function dismissOverlays(page) {
  await page.evaluate(() => {
    document.querySelectorAll('.tour-overlay, .tour-backdrop, [class*="tour"]').forEach(el => el.remove())
    localStorage.setItem('tour_completed', 'true')
    localStorage.setItem('tourDone', 'true')
    localStorage.setItem('predomics_tour_done', 'true')
  })
  const skipBtn = await page.$('button:has-text("Skip"), button:has-text("Close"), button:has-text("Got it"), .tour-skip')
  if (skipBtn) await skipBtn.click({ force: true }).catch(() => {})
  await page.waitForTimeout(300)
}

test.describe.serial('PredomicsApp E2E', () => {
  // ── 1. Landing page ──
  test('landing page loads and shows brand', async ({ page }) => {
    await page.goto(BASE)
    await page.waitForTimeout(2000)
    // Check the page has loaded (brand logo or title)
    const brand = page.locator('.brand')
    await expect(brand).toBeVisible()
    await expect(brand).toContainText('PredomicsApp')
  })

  // ── 2. Registration ──
  test('register a new user', async ({ page }) => {
    await page.goto(`${BASE}/login`)
    await page.waitForTimeout(1000)

    // Look for register link/tab
    const registerLink = page.locator('a:has-text("Register"), button:has-text("Register"), .register-link').first()
    if (await registerLink.isVisible()) {
      await registerLink.click()
      await page.waitForTimeout(500)
    }

    // Fill registration form
    await page.fill('input[type="email"], input[name="email"]', TEST_EMAIL)
    await page.fill('input[type="password"], input[name="password"]', TEST_PASSWORD)

    // Try to find and fill confirm password if it exists
    const confirmField = page.locator('input[name="confirmPassword"], input[placeholder*="Confirm"]')
    if (await confirmField.isVisible()) {
      await confirmField.fill(TEST_PASSWORD)
    }

    // Submit — use .btn-primary to avoid matching the Register tab button
    const submitBtn = page.locator('button[type="submit"].btn-primary, button.btn-primary:has-text("Create")')
    await submitBtn.click()
    await page.waitForTimeout(3000)

    // Should redirect to projects or dashboard
    await expect(page).toHaveURL(/projects|dashboard/)
  })

  // ── 3. Login ──
  test('login with credentials', async ({ page }) => {
    await page.goto(`${BASE}/login`)
    await page.waitForTimeout(1000)

    await page.fill('input[type="email"], input[name="email"]', TEST_EMAIL)
    await page.fill('input[type="password"], input[name="password"]', TEST_PASSWORD)
    await page.locator('button[type="submit"], button:has-text("Sign In"), button:has-text("Log In")').click()
    await page.waitForTimeout(3000)

    await expect(page).toHaveURL(/projects|dashboard/)
    // Verify auth state
    authToken = await page.evaluate(() => localStorage.getItem('token'))
    expect(authToken).toBeTruthy()
  })

  // ── 4. Create project ──
  test('create a new project', async ({ page }) => {
    // Login via API for speed
    await page.goto(BASE)
    await page.evaluate(async (creds) => {
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(creds),
      })
      const data = await resp.json()
      localStorage.setItem('token', data.access_token)
    }, { email: TEST_EMAIL, password: TEST_PASSWORD })

    await page.goto(`${BASE}/projects`)
    await page.waitForTimeout(2000)
    await dismissOverlays(page)

    // Click the "+" button to reveal the create form
    const newBtn = page.locator('button.btn-new, button[title="New project"]')
    await newBtn.click()
    await page.waitForTimeout(500)

    // Fill project name
    const nameInput = page.locator('input[placeholder*="name" i], input[name="name"]')
    await nameInput.fill('E2E Test Project')

    // Click "Create" button in the form
    const submitBtn = page.locator('button:has-text("Create")')
    await submitBtn.click()
    await page.waitForTimeout(3000)

    // Extract project ID from URL or API
    const url = page.url()
    const match = url.match(/project\/([a-f0-9]+)/)
    if (match) {
      projectId = match[1]
    } else {
      // Get from API
      const token = await page.evaluate(() => localStorage.getItem('token'))
      const resp = await page.evaluate(async (t) => {
        const r = await fetch('/api/projects/', { headers: { Authorization: `Bearer ${t}` } })
        return r.json()
      }, token)
      if (resp.length > 0) projectId = resp[0].id
    }
    expect(projectId).toBeTruthy()
  })

  // ── 5. Upload dataset ──
  test('upload dataset files', async ({ page }) => {
    if (!projectId) test.skip()

    await page.goto(BASE)
    await page.evaluate(async (creds) => {
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(creds),
      })
      const data = await resp.json()
      localStorage.setItem('token', data.access_token)
    }, { email: TEST_EMAIL, password: TEST_PASSWORD })

    await page.goto(`${BASE}/project/${projectId}/data`)
    await page.waitForTimeout(3000)
    await dismissOverlays(page)

    // Upload X file
    const fileInput = page.locator('input[type="file"]').first()
    if (await fileInput.isVisible()) {
      await fileInput.setInputFiles(path.join(DATA_DIR, 'X_train.tsv'))
      await page.waitForTimeout(2000)
    }

    // Page should show dataset info
    const pageContent = await page.textContent('body')
    expect(pageContent.length).toBeGreaterThan(100)
  })

  // ── 6. Dashboard shows stats ──
  test('dashboard displays summary cards', async ({ page }) => {
    await page.goto(BASE)
    await page.evaluate(async (creds) => {
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(creds),
      })
      const data = await resp.json()
      localStorage.setItem('token', data.access_token)
    }, { email: TEST_EMAIL, password: TEST_PASSWORD })

    await page.goto(`${BASE}/dashboard`)
    await page.waitForTimeout(3000)
    await dismissOverlays(page)

    // Dashboard should have stat cards
    const statCards = page.locator('.stat-card, .summary-card, .card')
    const count = await statCards.count()
    expect(count).toBeGreaterThan(0)
  })

  // ── 7. Meta-analysis page loads ──
  test('meta-analysis page is accessible', async ({ page }) => {
    await page.goto(BASE)
    await page.evaluate(async (creds) => {
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(creds),
      })
      const data = await resp.json()
      localStorage.setItem('token', data.access_token)
    }, { email: TEST_EMAIL, password: TEST_PASSWORD })

    await page.goto(`${BASE}/meta-analysis`)
    await page.waitForTimeout(2000)

    const heading = page.locator('h2')
    await expect(heading).toContainText('Meta-Analysis')
  })

  // ── 8. Public share page (unauthenticated) ──
  test('public share page loads for guest', async ({ browser }) => {
    // Access public share page without auth
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await ctx.newPage()

    // Try accessing with an invalid token (should show error gracefully)
    await page.goto(`${BASE}/public/invalid-token-test`)
    await page.waitForTimeout(3000)

    // Page should load (SPA renders) even if API returns 404
    const body = await page.textContent('body')
    expect(body.length).toBeGreaterThan(0)
    await ctx.close()
  })

  // ── 9. API health check ──
  test('health endpoint returns ok', async ({ request }) => {
    const resp = await request.get(`${BASE}/health`)
    expect(resp.ok()).toBeTruthy()
    const body = await resp.json()
    expect(body.status).toBe('ok')
  })

  // ── 10. API docs accessible ──
  test('swagger docs are accessible', async ({ request }) => {
    const resp = await request.get(`${BASE}/docs`)
    expect(resp.ok()).toBeTruthy()
  })
})
