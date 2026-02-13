<template>
  <div class="results-tab">
    <!-- Job selector -->
    <div class="job-selector" v-if="jobs.length > 0">
      <label>Job:
        <select v-model="selectedJobId" @change="loadJobResults">
          <option v-for="j in jobs" :key="j.job_id" :value="j.job_id">
            {{ j.job_id.slice(0, 8) }} &mdash; {{ j.status }}
            <template v-if="j.best_auc"> (AUC {{ j.best_auc.toFixed(4) }})</template>
          </option>
        </select>
      </label>
    </div>

    <!-- Sub-tabs -->
    <nav class="sub-tabs" v-if="detail">
      <button :class="{ active: subTab === 'summary' }" @click="subTab = 'summary'">Summary</button>
      <button :class="{ active: subTab === 'population' }" @click="subTab = 'population'">Population</button>
      <button :class="{ active: subTab === 'bestmodel' }" @click="subTab = 'bestmodel'">Best Model</button>
      <button :class="{ active: subTab === 'comparative' }" @click="subTab = 'comparative'">Comparative</button>
    </nav>

    <!-- Summary sub-tab -->
    <div v-if="detail && subTab === 'summary'" class="sub-content">
      <div class="summary-grid">
        <div class="stat-card">
          <div class="stat-value">{{ detail.best_auc?.toFixed(4) || '—' }}</div>
          <div class="stat-label">Best AUC</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ detail.best_k || '—' }}</div>
          <div class="stat-label">Features (k)</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ detail.execution_time?.toFixed(1) }}s</div>
          <div class="stat-label">Time</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ detail.generation_count }}</div>
          <div class="stat-label">Generations</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ detail.feature_count }}</div>
          <div class="stat-label">Total Features</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ detail.sample_count }}</div>
          <div class="stat-label">Samples</div>
        </div>
      </div>

      <!-- Convergence chart (Plotly) -->
      <section class="section" v-if="generationTracking.length > 0">
        <h3>Model Evolution (Train vs Test)</h3>
        <div ref="convergenceChartEl" class="plotly-chart"></div>
      </section>
    </div>

    <!-- Best Model sub-tab -->
    <div v-if="detail && subTab === 'bestmodel'" class="sub-content">
      <section class="section" v-if="detail.best_individual">
        <h3>Best Model Metrics</h3>
        <table class="metrics-table">
          <tr v-for="(val, key) in bestMetrics" :key="key">
            <td class="metric-name">{{ key }}</td>
            <td class="metric-value">{{ typeof val === 'number' ? val.toFixed(4) : val }}</td>
          </tr>
        </table>

        <h4>Selected Features</h4>
        <div class="feature-list">
          <div
            v-for="(coef, idx) in detail.best_individual.features"
            :key="idx"
            class="feature-chip"
            :class="{ positive: coef > 0, negative: coef < 0 }"
          >
            {{ featureName(idx) }} ({{ coef > 0 ? '+1' : '-1' }})
          </div>
        </div>
      </section>
    </div>

    <!-- Population sub-tab -->
    <div v-if="detail && subTab === 'population'" class="sub-content">
      <section class="section">
        <h3>Population of Models ({{ population.length }} individuals)</h3>
        <div v-if="population.length > 0">
          <table class="pop-table">
            <thead>
              <tr>
                <th>#</th>
                <th>AUC</th>
                <th>Fit</th>
                <th>Accuracy</th>
                <th>k</th>
                <th>Language</th>
                <th>Data Type</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="ind in paginatedPopulation" :key="ind.rank">
                <tr @click="toggleExpand(ind.rank)" class="clickable-row">
                  <td>{{ ind.rank + 1 }}</td>
                  <td>{{ ind.metrics.auc?.toFixed(4) }}</td>
                  <td>{{ ind.metrics.fit?.toFixed(4) }}</td>
                  <td>{{ ind.metrics.accuracy?.toFixed(4) }}</td>
                  <td>{{ ind.metrics.k }}</td>
                  <td>{{ ind.metrics.language }}</td>
                  <td>{{ ind.metrics.data_type }}</td>
                </tr>
                <tr v-if="expandedRank === ind.rank" class="detail-row">
                  <td colspan="7">
                    <div class="feature-list">
                      <div
                        v-for="(coef, name) in ind.named_features"
                        :key="name"
                        class="feature-chip"
                        :class="{ positive: coef > 0, negative: coef < 0 }"
                      >
                        {{ name }} ({{ coef > 0 ? '+1' : '-1' }})
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
          <div class="pagination" v-if="population.length > popPageSize">
            <button @click="popPage = Math.max(0, popPage - 1)" :disabled="popPage === 0">&laquo; Prev</button>
            <span>Page {{ popPage + 1 }} / {{ Math.ceil(population.length / popPageSize) }}</span>
            <button @click="popPage++" :disabled="(popPage + 1) * popPageSize >= population.length">Next &raquo;</button>
          </div>
        </div>
        <p v-else class="info-text">Population data not available for this job.</p>
      </section>
    </div>

    <!-- Comparative sub-tab -->
    <div v-if="detail && subTab === 'comparative'" class="sub-content">
      <section class="section">
        <h3>Comparative Analysis</h3>
        <p class="info-text">Multi-job comparison will be available in a future update.</p>
      </section>
    </div>

    <!-- Empty state -->
    <div v-if="!detail && jobs.length === 0" class="empty">
      No analysis jobs yet. Go to Data &amp; Run to launch an analysis.
    </div>
    <div v-if="!detail && jobs.length > 0 && !loading" class="empty">
      Select a completed job above to view results.
    </div>
    <div v-if="loading" class="loading">Loading results...</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '../stores/project'
import { useThemeStore } from '../stores/theme'
import axios from 'axios'
import Plotly from 'plotly.js-dist-min'

const route = useRoute()
const store = useProjectStore()
const themeStore = useThemeStore()

const loading = ref(false)
const detail = ref(null)
const population = ref([])
const generationTracking = ref([])
const subTab = ref('summary')
const selectedJobId = ref('')
const expandedRank = ref(null)
const popPage = ref(0)
const popPageSize = 50
const convergenceChartEl = ref(null)

const jobs = computed(() => {
  const allJobs = store.current?.jobs || []
  return allJobs.map(j => typeof j === 'string' ? { job_id: j, status: 'unknown' } : j)
})

const paginatedPopulation = computed(() => {
  const start = popPage.value * popPageSize
  return population.value.slice(start, start + popPageSize)
})

const bestMetrics = computed(() => {
  if (!detail.value?.best_individual) return {}
  const b = detail.value.best_individual
  return {
    AUC: b.auc,
    Fit: b.fit,
    Accuracy: b.accuracy,
    Sensitivity: b.sensitivity,
    Specificity: b.specificity,
    Threshold: b.threshold,
    Language: b.language,
    'Data Type': b.data_type,
    Epoch: b.epoch,
  }
})

function featureName(idx) {
  if (detail.value?.feature_names?.length > idx) {
    return detail.value.feature_names[idx]
  }
  return `feature_${idx}`
}

function toggleExpand(rank) {
  expandedRank.value = expandedRank.value === rank ? null : rank
}

async function renderConvergenceChart() {
  await nextTick()
  if (!convergenceChartEl.value || generationTracking.value.length === 0) return

  const gens = generationTracking.value.map(g => g.generation)
  const trainAuc = generationTracking.value.map(g => g.best_auc)
  const hasTest = generationTracking.value.some(g => g.best_auc_test != null)
  const testAuc = hasTest ? generationTracking.value.map(g => g.best_auc_test) : null

  const dark = themeStore.isDark
  const trainColor = dark ? '#4fc3f7' : '#1a1a2e'
  const testColor = dark ? '#ef5350' : '#e53935'
  const gridColor = dark ? '#3a3a52' : '#e0e0e0'
  const textColor = dark ? '#d0d0dc' : '#2c3e50'
  const paperBg = dark ? '#1e1e2e' : '#ffffff'

  const traces = [
    {
      x: gens,
      y: trainAuc,
      name: 'Train AUC',
      type: 'scatter',
      mode: 'lines+markers',
      line: { color: trainColor, width: 2 },
      marker: { size: 5 },
    },
  ]

  if (testAuc) {
    traces.push({
      x: gens,
      y: testAuc,
      name: 'Test AUC',
      type: 'scatter',
      mode: 'lines+markers',
      line: { color: testColor, width: 2, dash: 'dash' },
      marker: { size: 5 },
    })
  }

  const allValues = [...trainAuc, ...(testAuc || [])]
  const layout = {
    xaxis: {
      title: { text: 'Generation', font: { color: textColor } },
      dtick: Math.max(1, Math.floor(gens.length / 10)),
      gridcolor: gridColor,
      color: textColor,
    },
    yaxis: {
      title: { text: 'AUC', font: { color: textColor } },
      range: [
        Math.max(0, Math.min(...allValues) - 0.05),
        Math.min(1, Math.max(...allValues) + 0.02),
      ],
      gridcolor: gridColor,
      color: textColor,
    },
    margin: { t: 20, b: 50, l: 60, r: 20 },
    legend: { orientation: 'h', y: 1.12, font: { color: textColor } },
    height: 300,
    font: { family: 'system-ui, sans-serif', size: 12, color: textColor },
    paper_bgcolor: paperBg,
    plot_bgcolor: paperBg,
  }

  Plotly.newPlot(convergenceChartEl.value, traces, layout, {
    responsive: true,
    displayModeBar: false,
  })
}

watch([generationTracking, subTab, () => themeStore.isDark], () => {
  if (subTab.value === 'summary' && generationTracking.value.length > 0) {
    renderConvergenceChart()
  }
})

async function loadJobResults() {
  if (!selectedJobId.value) return
  loading.value = true
  const pid = route.params.id
  const jid = selectedJobId.value

  try {
    const { data } = await axios.get(`/api/analysis/${pid}/jobs/${jid}/detail`)
    detail.value = data

    // Try to load extended results (population + tracking)
    try {
      const { data: fullResults } = await axios.get(`/api/analysis/${pid}/jobs/${jid}/results`)
      population.value = fullResults.population || []
      generationTracking.value = fullResults.generation_tracking || []
    } catch {
      population.value = []
      generationTracking.value = []
    }
  } catch (e) {
    console.error('Failed to load results:', e)
    detail.value = null
  } finally {
    loading.value = false
  }
}

async function loadJobList() {
  const pid = route.params.id
  try {
    const { data } = await axios.get(`/api/analysis/${pid}/jobs`)
    if (store.current) {
      store.current.jobs = data
    }
    const jobIdFromRoute = route.params.jobId
    if (jobIdFromRoute) {
      selectedJobId.value = jobIdFromRoute
    } else if (data.length > 0) {
      const completed = data.find(j => j.status === 'completed')
      if (completed) selectedJobId.value = completed.job_id
    }
    if (selectedJobId.value) loadJobResults()
  } catch (e) {
    console.error('Failed to load jobs:', e)
  }
}

watch(() => route.params.jobId, (newId) => {
  if (newId && newId !== selectedJobId.value) {
    selectedJobId.value = newId
    loadJobResults()
  }
})

onMounted(loadJobList)
</script>

<style scoped>
.job-selector {
  margin-bottom: 1rem;
}

.job-selector label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.job-selector select {
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 0.9rem;
  min-width: 300px;
  background: var(--bg-input);
  color: var(--text-body);
}

.sub-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 1.5rem;
  border-bottom: 1px solid var(--border-light);
}

.sub-tabs button {
  padding: 0.5rem 1.25rem;
  border: none;
  background: none;
  color: var(--text-muted);
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}

.sub-tabs button.active {
  color: var(--text-primary);
  border-bottom-color: var(--accent);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card {
  background: var(--bg-card);
  padding: 1.25rem;
  border-radius: 8px;
  box-shadow: var(--shadow);
  text-align: center;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  font-size: 0.8rem;
  color: var(--text-faint);
  margin-top: 0.25rem;
}

.section {
  background: var(--bg-card);
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: var(--shadow);
  margin-bottom: 1.5rem;
}

.section h3 { margin-bottom: 1rem; color: var(--text-primary); }
.section h4 { margin: 1.5rem 0 0.75rem; color: var(--text-secondary); }

.plotly-chart {
  width: 100%;
  min-height: 300px;
}

.metrics-table { width: 100%; max-width: 400px; }
.metrics-table td { padding: 0.4rem 0; border-bottom: 1px solid var(--border-lighter); }
.metric-name { color: var(--text-muted); font-size: 0.9rem; }
.metric-value { text-align: right; font-weight: 600; color: var(--text-primary); }

.feature-list { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.feature-chip { padding: 0.35rem 0.75rem; border-radius: 20px; font-size: 0.85rem; font-weight: 500; }
.feature-chip.positive { background: var(--success-bg); color: var(--success-dark); }
.feature-chip.negative { background: var(--danger-bg); color: var(--danger-dark); }

.pop-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.pop-table th {
  text-align: left;
  padding: 0.5rem;
  border-bottom: 2px solid var(--border-light);
  color: var(--text-secondary);
  font-weight: 600;
}

.pop-table td {
  padding: 0.5rem;
  border-bottom: 1px solid var(--border-lighter);
  color: var(--text-body);
}

.clickable-row { cursor: pointer; }
.clickable-row:hover { background: var(--bg-card-hover); }

.detail-row td {
  background: var(--bg-badge);
  padding: 1rem;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-top: 1rem;
  font-size: 0.85rem;
}

.pagination button {
  padding: 0.3rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg-card);
  color: var(--text-body);
  cursor: pointer;
}

.pagination button:disabled { opacity: 0.5; cursor: not-allowed; }

.info-text { color: var(--text-faint); font-size: 0.85rem; font-style: italic; }
.empty { text-align: center; padding: 3rem; color: var(--text-faint); }
.loading { text-align: center; padding: 3rem; color: var(--text-faint); }
</style>
