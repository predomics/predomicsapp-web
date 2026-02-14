<template>
  <div class="params-tab">
    <form @submit.prevent="launch" novalidate>
      <div class="settings-grid">
        <!-- Left column: General, CV, Data filtering summary -->
        <div class="settings-col">
          <template v-for="cat in leftCategories" :key="cat.id">
            <ParamSection
              v-if="isCategoryVisible(cat)"
              :category="cat"
              :params="paramsByCategory[cat.id] || []"
              :form="cfg[cat.id]"
            />
          </template>

          <!-- Data filtering summary (read-only, not from parameterDefs) -->
          <section class="section info-section">
            <div class="section-title">Data Filtering</div>
            <div class="info-row"><span class="info-label">Method:</span> {{ cfg.data.feature_selection_method }}</div>
            <div class="info-row"><span class="info-label">Min prevalence:</span> {{ cfg.data.feature_minimal_prevalence_pct }}%</div>
            <div class="info-row"><span class="info-label">Max p-value:</span> {{ cfg.data.feature_maximal_adj_pvalue }}</div>
            <div class="info-row"><span class="info-label">Holdout ratio:</span> {{ cfg.data.holdout_ratio }}</div>
            <router-link :to="`/project/${route.params.id}/data`" class="edit-link">Edit in Data tab</router-link>
          </section>
        </div>

        <!-- Right column: Algo-specific, Importance, Voting, GPU -->
        <div class="settings-col">
          <template v-for="cat in rightCategories" :key="cat.id">
            <ParamSection
              v-if="isCategoryVisible(cat)"
              :category="cat"
              :params="paramsByCategory[cat.id] || []"
              :form="cfg[cat.id]"
            />
          </template>
        </div>
      </div>

      <!-- Job name + Launch bar -->
      <div class="launch-bar">
        <div class="job-name-row">
          <label class="job-name-label">Job name</label>
          <input
            v-model="jobName"
            type="text"
            class="job-name-input"
            :placeholder="autoJobName"
            maxlength="255"
          />
          <button type="button" class="btn btn-auto-name" @click="jobName = autoJobName" title="Generate from parameters">Auto</button>
        </div>
        <div class="launch-actions">
          <button type="submit" class="btn btn-launch" :disabled="launching || !canLaunch">
            {{ launching ? 'Launching...' : 'Launch Analysis' }}
          </button>
          <button type="button" class="btn btn-reset" @click="configStore.resetToDefaults()">Reset defaults</button>
          <span v-if="!canLaunch" class="launch-hint">Upload X and y training datasets in the Data tab first</span>
        </div>
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '../stores/project'
import { useConfigStore } from '../stores/config'
import { CATEGORIES, PARAM_DEFS } from '../data/parameterDefs'
import ParamSection from '../components/ParamSection.vue'
import axios from 'axios'

const route = useRoute()
const store = useProjectStore()
const configStore = useConfigStore()
const cfg = configStore.form
const launching = ref(false)
const jobName = ref('')

// Split categories into left/right columns
const leftCatIds = ['general', 'cv']
const rightCatIds = ['ga', 'beam', 'mcmc', 'importance', 'voting', 'gpu']
const leftCategories = computed(() => CATEGORIES.filter(c => leftCatIds.includes(c.id)))
const rightCategories = computed(() => CATEGORIES.filter(c => rightCatIds.includes(c.id)))

// Group params by category
const paramsByCategory = computed(() => {
  const map = {}
  for (const p of PARAM_DEFS) {
    if (!map[p.category]) map[p.category] = []
    map[p.category].push(p)
  }
  return map
})

// Visibility logic for conditional categories
function isCategoryVisible(cat) {
  if (cat.algoFilter) return cfg.general.algo === cat.algoFilter
  if (cat.enabledBy) {
    const [section, key] = cat.enabledBy.split('.')
    return cfg[section]?.[key] === true
  }
  return true
}

// Auto-generate job name from config diff vs defaults
const autoJobName = computed(() => {
  const parts = []
  // Algorithm
  const algo = cfg.general.algo?.toUpperCase() || 'GA'
  parts.push(algo)
  // Languages
  const lang = cfg.general.language || ''
  if (lang !== 'bin,ter,ratio') parts.push(lang.replace(/,/g, '+'))
  // Data types
  const dt = cfg.general.data_type || ''
  if (dt !== 'raw,prev') parts.push(dt.replace(/,/g, '+'))
  // Fit function
  if (cfg.general.fit && cfg.general.fit !== 'auc') parts.push(cfg.general.fit)
  // k range (GA only)
  if (algo === 'GA') {
    const kMin = cfg.ga.k_min ?? 1
    const kMax = cfg.ga.k_max ?? 200
    if (kMin !== 1 || kMax !== 200) parts.push(`k${kMin}-${kMax}`)
    // Population size
    if (cfg.ga.population_size !== 5000) parts.push(`pop${cfg.ga.population_size}`)
    // Epochs
    if (cfg.ga.max_epochs !== 200) parts.push(`${cfg.ga.max_epochs}ep`)
  }
  // Seed
  if (cfg.general.seed !== 42) parts.push(`s${cfg.general.seed}`)
  // CV
  if (cfg.general.cv) parts.push('CV')
  // Voting
  if (cfg.voting.vote) parts.push('vote')
  return parts.join(' ')
})

// File resolution for launch
const datasets = computed(() => store.current?.datasets || [])
const allFiles = computed(() =>
  datasets.value.flatMap(ds => (ds.files || []).map(f => ({ ...f, datasetId: ds.id })))
)
function findFile(role) { return allFiles.value.find(f => f.role === role) || null }
const xTrainDs = computed(() => findFile('xtrain'))
const yTrainDs = computed(() => findFile('ytrain'))
const xTestDs = computed(() => findFile('xtest'))
const yTestDs = computed(() => findFile('ytest'))
const canLaunch = computed(() => xTrainDs.value && yTrainDs.value)

async function launch() {
  if (!canLaunch.value) return
  launching.value = true
  try {
    const params = { x_file_id: xTrainDs.value.id, y_file_id: yTrainDs.value.id }
    if (xTestDs.value) params.xtest_file_id = xTestDs.value.id
    if (yTestDs.value) params.ytest_file_id = yTestDs.value.id
    const name = jobName.value.trim() || autoJobName.value
    if (name) params.job_name = name

    const { data } = await axios.post(
      `/api/analysis/${route.params.id}/run`,
      cfg,
      { params }
    )
    store.startJob(data.job_id)
  } catch (e) {
    alert('Failed to launch: ' + (e.response?.data?.detail || e.message))
  } finally {
    launching.value = false
  }
}
</script>

<style scoped>
.params-tab { max-width: 100%; }

.settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1rem;
}

.settings-col {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.info-section { background: var(--bg-badge); padding: 1rem 1.25rem; border-radius: 8px; box-shadow: var(--shadow); }
.section-title {
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--text-primary);
  margin-bottom: 0.75rem;
}
.info-row {
  font-size: 0.8rem;
  color: var(--text-body);
  margin-bottom: 0.3rem;
}
.info-label {
  color: var(--text-muted);
  display: inline-block;
  min-width: 100px;
}
.edit-link {
  font-size: 0.8rem;
  color: var(--accent);
  text-decoration: none;
  margin-top: 0.5rem;
  display: inline-block;
}
.edit-link:hover { text-decoration: underline; }

.launch-bar {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.75rem 0;
}

.job-name-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.job-name-label {
  font-size: 0.85rem;
  color: var(--text-secondary);
  white-space: nowrap;
  font-weight: 500;
}
.job-name-input {
  flex: 1;
  max-width: 400px;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.85rem;
  background: var(--bg-input);
  color: var(--text-body);
}
.job-name-input::placeholder { color: var(--text-faint); }
.btn-auto-name {
  padding: 0.35rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.75rem;
  cursor: pointer;
  background: transparent;
  color: var(--text-secondary);
  transition: all 0.2s;
}
.btn-auto-name:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.launch-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.btn-launch {
  padding: 0.65rem 2rem;
  border: none;
  border-radius: 6px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  background: var(--accent);
  color: var(--accent-text);
  transition: opacity 0.15s;
}

.btn-launch:hover:not(:disabled) { opacity: 0.9; }
.btn-launch:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-reset {
  padding: 0.5rem 1rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
  background: transparent;
  color: var(--text-secondary);
  transition: all 0.2s;
}
.btn-reset:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.launch-hint { color: var(--warning-dark); font-size: 0.8rem; }

@media (max-width: 900px) {
  .settings-grid { grid-template-columns: 1fr; }
}
</style>
