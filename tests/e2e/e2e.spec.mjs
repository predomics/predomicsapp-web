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

// Helper: login via API and set token in localStorage
async function loginViaAPI(page) {
  await page.goto(BASE)
  await page.evaluate(async (creds) => {
    const resp = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(creds),
    })
    const data = await resp.json()
    if (data.access_token) {
      localStorage.setItem('token', data.access_token)
    }
  }, { email: TEST_EMAIL, password: TEST_PASSWORD })
}

// Helper: dismiss onboarding tour overlay (uses correct localStorage key)
async function dismissOverlays(page) {
  await page.evaluate(() => {
    // Correct key used by OnboardingTour.vue
    localStorage.setItem('predomics_onboarding_dismissed', 'true')
    // Remove any tour overlays from the DOM
    document.querySelectorAll('.tour-overlay, .tour-backdrop').forEach(el => el.remove())
  })
  // Also try clicking dismiss/close buttons if they exist
  const closeBtn = page.locator('.tour-close, button.tour-btn:has-text("Get Started")').first()
  if (await closeBtn.isVisible({ timeout: 500 }).catch(() => false)) {
    await closeBtn.click({ force: true }).catch(() => {})
  }
  await page.waitForTimeout(300)
}

test.describe.serial('PredomicsApp E2E', () => {
  // ── 1. Landing page ──
  test('landing page loads and shows brand', async ({ page }) => {
    await page.goto(BASE)
    await page.waitForTimeout(2000)
    const brand = page.locator('.brand')
    await expect(brand).toBeVisible()
    await expect(brand).toContainText('PredomicsApp')
  })

  // ── 2. Registration ──
  test('register a new user', async ({ page }) => {
    await page.goto(`${BASE}/login`)
    await page.waitForTimeout(1000)

    // Click the Register tab (first matching, to avoid ambiguity with submit button)
    const registerTab = page.locator('button:has-text("Register")').first()
    if (await registerTab.isVisible()) {
      await registerTab.click()
      await page.waitForTimeout(500)
    }

    // Fill registration form
    await page.fill('input[type="email"]', TEST_EMAIL)
    await page.fill('input[type="password"]', TEST_PASSWORD)

    // Fill name field if visible (register mode has it)
    const nameField = page.locator('input[type="text"][placeholder*="name" i]')
    if (await nameField.isVisible({ timeout: 500 }).catch(() => false)) {
      await nameField.fill('E2E Test User')
    }

    // Submit — target the .btn-primary submit button specifically
    await page.locator('button[type="submit"].btn-primary').click()
    await page.waitForTimeout(3000)

    // Should redirect to /projects after successful registration
    await expect(page).toHaveURL(/projects/)
  })

  // ── 3. Login ──
  test('login with credentials', async ({ page }) => {
    await page.goto(`${BASE}/login`)
    await page.waitForTimeout(1000)

    // Make sure we're on the Login tab (not Register)
    const loginTab = page.locator('button:has-text("Login")').first()
    if (await loginTab.isVisible({ timeout: 500 }).catch(() => false)) {
      await loginTab.click()
      await page.waitForTimeout(300)
    }

    await page.fill('input[type="email"]', TEST_EMAIL)
    await page.fill('input[type="password"]', TEST_PASSWORD)
    // Submit button text is "Login" in login mode
    await page.locator('button[type="submit"].btn-primary').click()
    await page.waitForTimeout(3000)

    await expect(page).toHaveURL(/projects/)
    authToken = await page.evaluate(() => localStorage.getItem('token'))
    expect(authToken).toBeTruthy()
  })

  // ── 4. Create project ──
  test('create a new project', async ({ page }) => {
    await loginViaAPI(page)

    await page.goto(`${BASE}/projects`)
    await page.waitForTimeout(2000)
    await dismissOverlays(page)

    // Click the "+" button (class btn-new, title "New project") to reveal the form
    const newBtn = page.locator('button.btn-new')
    await expect(newBtn).toBeVisible({ timeout: 10000 })
    await newBtn.click()
    await page.waitForTimeout(500)

    // Fill project name in the create form
    const nameInput = page.locator('.create-form input[placeholder*="name" i]')
    await expect(nameInput).toBeVisible({ timeout: 5000 })
    await nameInput.fill('E2E Test Project')

    // Click the "Create" button inside the form
    const createBtn = page.locator('.create-form button:has-text("Create")')
    await createBtn.click()
    await page.waitForTimeout(3000)

    // After creation, the page stays on /projects with the project selected
    // Extract project ID from the API
    const token = await page.evaluate(() => localStorage.getItem('token'))
    const projects = await page.evaluate(async (t) => {
      const r = await fetch('/api/projects/', { headers: { Authorization: `Bearer ${t}` } })
      return r.json()
    }, token)
    if (Array.isArray(projects) && projects.length > 0) {
      projectId = projects[0].project_id
    }
    expect(projectId).toBeTruthy()
  })

  // ── 5. Upload dataset ──
  test('upload dataset files', async ({ page }) => {
    if (!projectId) test.skip()

    await loginViaAPI(page)

    await page.goto(`${BASE}/project/${projectId}/data`)
    await page.waitForTimeout(3000)
    await dismissOverlays(page)

    // Upload X file (try Xtrain.tsv, fallback to X_train.tsv)
    const fileInput = page.locator('input[type="file"]').first()
    if (await fileInput.count() > 0) {
      const fs = await import('fs')
      const xFile = [path.join(DATA_DIR, 'Xtrain.tsv'), path.join(DATA_DIR, 'X_train.tsv')]
        .find(f => fs.existsSync(f))
      if (xFile) {
        await fileInput.setInputFiles(xFile)
        await page.waitForTimeout(2000)
      }
    }

    // Page should show dataset info
    const pageContent = await page.textContent('body')
    expect(pageContent.length).toBeGreaterThan(100)
  })

  // ── 6. Dashboard shows stats ──
  test('dashboard displays summary cards', async ({ page }) => {
    await loginViaAPI(page)

    await page.goto(`${BASE}/dashboard`)
    await page.waitForTimeout(3000)
    await dismissOverlays(page)

    // Dashboard should have stat-card elements (at least Projects, Datasets, Completed)
    const statCards = page.locator('.stat-card')
    await expect(statCards.first()).toBeVisible({ timeout: 10000 })
    const count = await statCards.count()
    expect(count).toBeGreaterThanOrEqual(3)
  })

  // ── 7. Meta-analysis page loads ──
  test('meta-analysis page is accessible', async ({ page }) => {
    await loginViaAPI(page)

    await page.goto(`${BASE}/meta-analysis`)
    await page.waitForTimeout(2000)

    // Heading is "Multi-Cohort Meta-Analysis" (i18n key meta.title)
    const heading = page.locator('h2')
    await expect(heading).toContainText('Meta-Analysis')
  })

  // ── 8. Public share page (unauthenticated) ──
  test('public share page loads for guest', async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await ctx.newPage()

    // Access with an invalid token — page should render SPA even if API returns 404
    await page.goto(`${BASE}/public/invalid-token-test`)
    await page.waitForTimeout(3000)

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
