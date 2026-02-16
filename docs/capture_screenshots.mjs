/**
 * Capture screenshots of PredomicsApp pages for documentation.
 * Usage: node docs/capture_screenshots.mjs
 *
 * Prerequisites: npm install playwright
 * The app must be running at BASE URL (default http://localhost:8001).
 */
import { chromium } from 'playwright';

const BASE = 'http://localhost:8001';
const OUT  = 'docs/screenshots';
const CREDS = { email: 'edi.prifti@gmail.com', password: 'editest' };
const PROJECT_ID = 'd0810056bcc1';
const JOB_ID     = '4180f1e459ac';

async function dismissOverlays(page) {
  await page.evaluate(() => {
    document.querySelectorAll('.tour-overlay, .tour-backdrop, [class*="tour"]').forEach(el => el.remove());
    localStorage.setItem('tour_completed', 'true');
    localStorage.setItem('tourDone', 'true');
    localStorage.setItem('predomics_tour_done', 'true');
  });
  const skipBtn = await page.$('button:has-text("Skip"), button:has-text("Close"), button:has-text("Got it"), .tour-skip');
  if (skipBtn) await skipBtn.click({ force: true }).catch(() => {});
  await page.waitForTimeout(300);
}

async function main() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    colorScheme: 'dark',
  });
  const page = await ctx.newPage();

  // ── 1. Landing / Home page (unauthenticated) ──
  await page.goto(BASE);
  await page.waitForTimeout(2000);
  await dismissOverlays(page);
  await page.screenshot({ path: `${OUT}/01_landing.png` });
  console.log('1/17 Landing page ✓');

  // ── 2. Login page ──
  await page.goto(`${BASE}/login`);
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${OUT}/02_login.png` });
  console.log('2/17 Login page ✓');

  // ── Authenticate via API and inject token into localStorage ──
  await page.evaluate(async (creds) => {
    const resp = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(creds),
    });
    if (!resp.ok) throw new Error(`Login failed: ${resp.status}`);
    const data = await resp.json();
    localStorage.setItem('token', data.access_token);
  }, CREDS);
  console.log('   Authenticated (token injected)');

  // ── 3. Dashboard ──
  await page.goto(`${BASE}/dashboard`);
  await page.waitForTimeout(3000);
  await dismissOverlays(page);
  await page.screenshot({ path: `${OUT}/12_dashboard.png` });
  console.log('3/17 Dashboard ✓');

  // ── 4. Projects page ──
  await page.goto(`${BASE}/projects`);
  await page.waitForTimeout(3000);
  await dismissOverlays(page);
  await page.screenshot({ path: `${OUT}/03_projects.png` });
  console.log('4/17 Projects list ✓');

  // ── 5. Project Data & Run tab ──
  await page.goto(`${BASE}/project/${PROJECT_ID}/data`);
  await page.waitForTimeout(4000);
  await dismissOverlays(page);
  await page.screenshot({ path: `${OUT}/04_project_data.png` });
  console.log('5/17 Project data tab ✓');

  // ── 6. Parameters tab ──
  await page.goto(`${BASE}/project/${PROJECT_ID}/parameters`);
  await page.waitForTimeout(3000);
  await dismissOverlays(page);
  await page.screenshot({ path: `${OUT}/05_parameters.png` });
  console.log('6/17 Parameters tab ✓');

  // ── 7. Results — Summary ──
  await page.goto(`${BASE}/project/${PROJECT_ID}/results/${JOB_ID}`);
  await page.waitForTimeout(6000);
  await dismissOverlays(page);
  // Scroll past the jobs table to show the results sub-tab content
  await page.evaluate(() => {
    const subTabs = document.querySelector('button.active')?.closest('.sub-tabs, [class*="sub"]');
    if (subTabs) subTabs.scrollIntoView({ block: 'start' });
    else window.scrollBy(0, 600);
  });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${OUT}/06_results_summary.png` });
  console.log('7/17 Results summary ✓');

  // Helper: click a sub-tab and scroll to content area
  async function clickSubTab(label) {
    await page.evaluate((lbl) => {
      const btns = [...document.querySelectorAll('button')];
      const btn = btns.find(b => b.textContent.trim() === lbl);
      if (btn) {
        btn.click();
        btn.scrollIntoView({ block: 'start' });
      }
    }, label);
  }

  // ── 7. Best Model sub-tab ──
  try {
    await clickSubTab('Best Model');
    await page.waitForTimeout(4000);
    await page.evaluate(() => window.scrollBy(0, -60));
    await page.screenshot({ path: `${OUT}/07_best_model.png` });
    console.log('8/17 Best Model ✓');
  } catch { console.log('8/17 Best Model — SKIPPED (no button)'); }

  // ── 8. Population sub-tab ──
  try {
    await clickSubTab('Population');
    await page.waitForTimeout(4000);
    await page.evaluate(() => window.scrollBy(0, -60));
    await page.screenshot({ path: `${OUT}/08_population.png` });
    console.log('9/17 Population ✓');
  } catch { console.log('9/17 Population — SKIPPED'); }

  // ── 9. Co-presence sub-tab ──
  try {
    await clickSubTab('Co-presence');
    await page.waitForTimeout(6000);
    await page.evaluate(() => window.scrollBy(0, -60));
    await page.screenshot({ path: `${OUT}/09_copresence.png` });
    console.log('10/17 Co-presence ✓');

    // Scroll to see heatmap + network
    await page.evaluate(() => window.scrollBy(0, 900));
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${OUT}/10_copresence_network.png` });
    console.log('11/17 Co-presence network ✓');
  } catch (e) { console.log('10-11/17 Co-presence — SKIPPED:', e.message); }

  // ── 11. Comparative sub-tab ──
  try {
    await clickSubTab('Comparative');
    await page.waitForTimeout(4000);
    await page.evaluate(() => window.scrollBy(0, -60));
    await page.screenshot({ path: `${OUT}/11_comparative.png` });
    console.log('12/17 Comparative ✓');
  } catch { console.log('12/17 Comparative — SKIPPED'); }

  // ── 13. Create a public share link and capture the public view ──
  try {
    // Create a public link via API
    const token = await page.evaluate(async (pid) => {
      const authToken = localStorage.getItem('token');
      const resp = await fetch(`/api/projects/${pid}/public`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify({ expires_in_days: null }),
      });
      if (!resp.ok) return null;
      const data = await resp.json();
      return data.token;
    }, PROJECT_ID);

    if (token) {
      // Open public share page in a new context (unauthenticated)
      const pubCtx = await browser.newContext({
        viewport: { width: 1440, height: 900 },
        colorScheme: 'dark',
      });
      const pubPage = await pubCtx.newPage();
      await pubPage.goto(`${BASE}/public/${token}`);
      await pubPage.waitForTimeout(5000);
      await pubPage.screenshot({ path: `${OUT}/13_public_share.png` });
      await pubCtx.close();
      console.log('13/17 Public share ✓');
    } else {
      console.log('13/17 Public share — SKIPPED (failed to create link)');
    }
  } catch (e) { console.log('13/17 Public share — SKIPPED:', e.message); }

  // ── 14. Meta-Analysis page ──
  try {
    await page.goto(`${BASE}/meta-analysis`);
    await page.waitForTimeout(4000);
    await dismissOverlays(page);
    await page.screenshot({ path: `${OUT}/14_meta_analysis.png` });
    console.log('14/17 Meta-Analysis ✓');
  } catch { console.log('14/17 Meta-Analysis — SKIPPED'); }

  // ── 15. SHAP explanations (Best Model sub-tab) ──
  try {
    await page.goto(`${BASE}/project/${PROJECT_ID}/results/${JOB_ID}`);
    await page.waitForTimeout(4000);
    await clickSubTab('Best Model');
    await page.waitForTimeout(3000);
    // Scroll down to SHAP section
    await page.evaluate(() => {
      const shapEl = document.querySelector('[class*="shap"], h3:has-text("SHAP"), h4:has-text("SHAP")');
      if (shapEl) shapEl.scrollIntoView({ block: 'start' });
      else window.scrollBy(0, 1200);
    });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${OUT}/15_shap.png` });
    console.log('15/17 SHAP explanations ✓');
  } catch { console.log('15/17 SHAP — SKIPPED'); }

  // ── 16. French UI (switch locale and capture dashboard) ──
  try {
    await page.evaluate(() => localStorage.setItem('locale', 'fr'));
    await page.goto(`${BASE}/dashboard`);
    await page.waitForTimeout(3000);
    await dismissOverlays(page);
    await page.screenshot({ path: `${OUT}/16_french_dashboard.png` });
    console.log('16/17 French dashboard ✓');

    await page.goto(`${BASE}/projects`);
    await page.waitForTimeout(3000);
    await dismissOverlays(page);
    await page.screenshot({ path: `${OUT}/17_french_projects.png` });
    console.log('17/17 French projects ✓');

    // Reset locale back to English
    await page.evaluate(() => localStorage.setItem('locale', 'en'));
  } catch { console.log('16-17/17 French UI — SKIPPED'); }

  await browser.close();
  console.log(`\nDone! Screenshots saved to ${OUT}/`);
}

main().catch(e => { console.error(e); process.exit(1); });
