<template>
  <div class="ecosystem-tab">
    <!-- Controls -->
    <div class="eco-controls">
      <div class="eco-controls-row">
        <label class="eco-control">
          {{ $t('results.ecoPrevalence') }}
          <input type="range" v-model.number="prevalenceThreshold" min="5" max="80" step="5" />
          <span class="eco-value">{{ prevalenceThreshold }}%</span>
        </label>
        <label class="eco-control">
          {{ $t('results.ecoCorrelation') }}
          <input type="range" v-model.number="correlationThreshold" min="0.1" max="0.8" step="0.05" />
          <span class="eco-value">{{ correlationThreshold.toFixed(2) }}</span>
        </label>
        <label class="eco-control">
          {{ $t('results.ecoClassFilter') }}
          <select v-model="classFilter">
            <option value="all">{{ $t('results.ecoAllSamples') }}</option>
            <option value="0">{{ classLabels[0] || 'Class 0' }}</option>
            <option value="1">{{ classLabels[1] || 'Class 1' }}</option>
          </select>
        </label>
        <label class="eco-control">
          {{ $t('results.ecoColorBy') }}
          <select v-model="colorMode">
            <option value="taxonomy">{{ $t('results.ecoTaxonomy') }}</option>
            <option value="module">{{ $t('results.ecoModule') }}</option>
            <option value="enrichment">{{ $t('results.ecoEnrichment') }}</option>
          </select>
        </label>
        <label class="eco-control">
          {{ $t('results.ecoLayout') }}
          <select v-model="layoutMode">
            <option value="organic">{{ $t('results.ecoOrganic') }}</option>
            <option value="force">{{ $t('results.forceDirected') }}</option>
            <option value="circle">{{ $t('results.circle') }}</option>
            <option value="radial">{{ $t('results.radial') }}</option>
          </select>
        </label>
        <label class="eco-control" v-if="jobId">
          <input type="checkbox" v-model="fbmOverlay" />
          {{ $t('results.ecoFbmOverlay') }}
        </label>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading">{{ $t('results.ecoLoading') }}</div>

    <!-- Error -->
    <div v-if="error" class="error-text">{{ error }}</div>

    <!-- Network Chart -->
    <div v-show="!loading && !error && networkData" class="eco-chart-wrap">
      <div ref="networkChartEl" class="eco-chart"></div>
    </div>

    <!-- Stats bar -->
    <div v-if="networkData && !loading" class="eco-stats-bar">
      <span><strong>{{ networkData.stats.n_nodes }}</strong> {{ $t('results.ecoNodes') }}</span>
      <span><strong>{{ networkData.stats.n_edges }}</strong> {{ $t('results.ecoEdges') }}</span>
      <span><strong>{{ networkData.stats.n_modules }}</strong> {{ $t('results.ecoModules') }}</span>
      <span>{{ $t('results.ecoModularity') }}: <strong>{{ networkData.stats.modularity }}</strong></span>
      <span>{{ $t('results.ecoFeaturesFiltered') }}: <strong>{{ networkData.stats.n_features_filtered }}</strong> / {{ networkData.stats.n_features_total }}</span>
    </div>

    <!-- Module + Legend section -->
    <div v-if="networkData && !loading" class="eco-bottom">
      <!-- Module list -->
      <section class="eco-modules">
        <h4>{{ $t('results.ecoModulesTitle') }}</h4>
        <div v-for="mod in networkData.modules" :key="mod.id" class="eco-module-item"
             :class="{ highlighted: highlightedModule === mod.id }"
             @click="toggleModuleHighlight(mod.id)">
          <span class="eco-module-dot" :style="{ backgroundColor: mod.color }"></span>
          <span>{{ $t('results.ecoModule') }} {{ mod.id + 1 }}</span>
          <span class="eco-module-size">{{ mod.size }} {{ $t('results.ecoNodes') }}</span>
          <span class="eco-module-phylum">{{ mod.dominant_phylum }}</span>
        </div>
      </section>

      <!-- Taxonomy legend -->
      <section class="eco-legend" v-if="colorMode === 'taxonomy'">
        <h4>{{ $t('results.ecoTaxonomyLegend') }}</h4>
        <div class="eco-legend-grid">
          <div v-for="entry in networkData.taxonomy_legend" :key="entry.family" class="eco-legend-item">
            <span class="eco-legend-dot" :style="{ backgroundColor: entry.color }"></span>
            <span class="eco-legend-family">{{ entry.family }}</span>
            <span class="eco-legend-phylum">{{ entry.phylum }}</span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'
import { useChartTheme } from '../../composables/useChartTheme'
import { useI18n } from 'vue-i18n'
import { MODULE_COLORS } from '../../utils/taxonomyColors'
import axios from 'axios'

let Plotly = null
async function ensurePlotly() {
  if (!Plotly) {
    const mod = await import('plotly.js-dist-min')
    Plotly = mod.default
  }
  return Plotly
}

const props = defineProps({
  projectId: { type: String, required: true },
  jobId: { type: String, default: '' },
  population: { type: Array, default: () => [] },
  classLabels: { type: Array, default: () => [] },
  active: { type: Boolean, default: false },
})

const { chartColors, chartLayout } = useChartTheme()
const { t } = useI18n()

// Controls
const prevalenceThreshold = ref(30)
const correlationThreshold = ref(0.3)
const classFilter = ref('all')
const colorMode = ref('taxonomy')
const layoutMode = ref('organic')
const fbmOverlay = ref(false)
const highlightedModule = ref(null)

// State
const loading = ref(false)
const error = ref(null)
const networkData = ref(null)
const networkChartEl = ref(null)

// Debounce timer
let fetchTimer = null

function toggleModuleHighlight(modId) {
  highlightedModule.value = highlightedModule.value === modId ? null : modId
  if (networkData.value) renderNetwork()
}

async function fetchNetwork() {
  loading.value = true
  error.value = null

  try {
    const params = {
      min_prevalence_pct: prevalenceThreshold.value,
      correlation_threshold: correlationThreshold.value,
      class_filter: classFilter.value,
    }

    // Add FBM features if overlay is enabled
    if (fbmOverlay.value && props.jobId) {
      params.job_id = props.jobId
    }

    // Add FBM feature names if available
    if (props.population.length > 0) {
      const allFeatures = new Set()
      for (const ind of props.population) {
        const named = ind.named_features || {}
        for (const f of Object.keys(named)) allFeatures.add(f)
      }
      if (allFeatures.size > 0 && allFeatures.size < 500) {
        // Only send features filter if FBM overlay and reasonable size
        // For full ecosystem view, we compute on all features
      }
    }

    const { data } = await axios.get(`/api/data-explore/${props.projectId}/coabundance-network`, { params })
    networkData.value = data

    await nextTick()
    await renderNetwork()
  } catch (err) {
    console.error('Ecosystem network error:', err)
    error.value = err.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

function debouncedFetch() {
  clearTimeout(fetchTimer)
  fetchTimer = setTimeout(fetchNetwork, 400)
}

// --- Layout algorithms ---

// Seeded PRNG for reproducible layouts
function mulberry32(seed) {
  return function() {
    let t = seed += 0x6D2B79F5
    t = Math.imul(t ^ t >>> 15, t | 1)
    t ^= t + Math.imul(t ^ t >>> 7, t | 61)
    return ((t ^ t >>> 14) >>> 0) / 4294967296
  }
}

function layoutCircle(n) {
  const x = [], y = []
  for (let i = 0; i < n; i++) {
    const angle = (2 * Math.PI * i) / n
    x.push(Math.cos(angle))
    y.push(Math.sin(angle))
  }
  return { x, y }
}

function layoutRadial(nodes) {
  const n = nodes.length
  if (n === 0) return { x: [], y: [] }

  const sorted = [...nodes].sort((a, b) => (b.degree || 0) - (a.degree || 0))
  const positions = {}
  positions[sorted[0].id] = { x: 0, y: 0 }

  let ringIdx = 0, placed = 1
  while (placed < n) {
    ringIdx++
    const radius = ringIdx * 1.5
    const ringCapacity = Math.max(6, Math.floor(2 * Math.PI * radius / 0.8))
    const ringCount = Math.min(ringCapacity, n - placed)
    for (let i = 0; i < ringCount; i++) {
      const angle = (2 * Math.PI * i) / ringCount
      positions[sorted[placed].id] = { x: radius * Math.cos(angle), y: radius * Math.sin(angle) }
      placed++
    }
  }
  return {
    x: nodes.map(nd => positions[nd.id]?.x || 0),
    y: nodes.map(nd => positions[nd.id]?.y || 0),
  }
}

/**
 * Fruchterman-Reingold organic layout.
 * Random initialization, attractive/repulsive forces, simulated annealing.
 * Produces natural, non-circular network shapes.
 */
function layoutOrganic(nodes, edges) {
  const n = nodes.length
  if (n === 0) return { x: [], y: [] }

  const idxMap = {}
  nodes.forEach((nd, i) => { idxMap[nd.id] = i })

  // Build adjacency for quick lookup
  const adj = Array.from({ length: n }, () => [])
  for (const edge of edges) {
    const i = idxMap[edge.source], j = idxMap[edge.target]
    if (i !== undefined && j !== undefined) {
      adj[i].push({ j, w: Math.abs(edge.correlation) })
      adj[j].push({ i: i, w: Math.abs(edge.correlation) })
    }
  }

  // Optimal distance (Fruchterman-Reingold k parameter)
  const area = n * 8
  const k = Math.sqrt(area / n)
  const k2 = k * k

  // Random initial positions (seeded for reproducibility)
  const rng = mulberry32(42)
  const spread = Math.sqrt(n) * 2
  const nodeX = Array.from({ length: n }, () => (rng() - 0.5) * spread)
  const nodeY = Array.from({ length: n }, () => (rng() - 0.5) * spread)

  // Simulated annealing temperature
  let temperature = spread * 0.2
  const cooling = 0.95
  const iterations = 200

  for (let iter = 0; iter < iterations; iter++) {
    const fx = new Array(n).fill(0)
    const fy = new Array(n).fill(0)

    // Repulsive forces between all pairs
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = nodeX[i] - nodeX[j]
        let dy = nodeY[i] - nodeY[j]
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 0.01)
        // FR repulsion: k^2 / dist
        const repForce = k2 / dist
        const rx = (dx / dist) * repForce
        const ry = (dy / dist) * repForce
        fx[i] += rx; fy[i] += ry
        fx[j] -= rx; fy[j] -= ry
      }
    }

    // Attractive forces along edges
    for (const edge of edges) {
      const i = idxMap[edge.source], j = idxMap[edge.target]
      if (i === undefined || j === undefined) continue
      let dx = nodeX[j] - nodeX[i]
      let dy = nodeY[j] - nodeY[i]
      const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 0.01)
      // FR attraction: dist^2 / k, weighted by correlation strength
      const attForce = (dist * dist / k) * (0.5 + Math.abs(edge.correlation) * 0.5)
      const ax = (dx / dist) * attForce
      const ay = (dy / dist) * attForce
      fx[i] += ax; fy[i] += ay
      fx[j] -= ax; fy[j] -= ay
    }

    // Mild gravity toward center to prevent drift
    const gravity = 0.02
    for (let i = 0; i < n; i++) {
      fx[i] -= nodeX[i] * gravity
      fy[i] -= nodeY[i] * gravity
    }

    // Apply displacement, limited by temperature
    for (let i = 0; i < n; i++) {
      const disp = Math.sqrt(fx[i] * fx[i] + fy[i] * fy[i])
      if (disp > 0) {
        const capped = Math.min(disp, temperature)
        nodeX[i] += (fx[i] / disp) * capped
        nodeY[i] += (fy[i] / disp) * capped
      }
    }

    temperature *= cooling
  }

  return { x: nodeX, y: nodeY }
}

function layoutForceDirected(nodes, edges) {
  const n = nodes.length
  if (n === 0) return { x: [], y: [] }

  const idxMap = {}
  nodes.forEach((nd, i) => { idxMap[nd.id] = i })

  // Random initial positions (not circle) for non-circular result
  const rng = mulberry32(123)
  const spread = Math.sqrt(n) * 2
  const nodeX = Array.from({ length: n }, () => (rng() - 0.5) * spread)
  const nodeY = Array.from({ length: n }, () => (rng() - 0.5) * spread)

  for (let iter = 0; iter < 120; iter++) {
    const fx = new Array(n).fill(0)
    const fy = new Array(n).fill(0)

    // Repulsion
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const dx = nodeX[i] - nodeX[j]
        const dy = nodeY[i] - nodeY[j]
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 0.3)
        const force = 400 / (dist * dist)
        fx[i] += force * dx / dist
        fy[i] += force * dy / dist
        fx[j] -= force * dx / dist
        fy[j] -= force * dy / dist
      }
    }

    // Attraction along edges
    for (const edge of edges) {
      const i = idxMap[edge.source], j = idxMap[edge.target]
      if (i === undefined || j === undefined) continue
      const dx = nodeX[j] - nodeX[i]
      const dy = nodeY[j] - nodeY[i]
      const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 0.3)
      const sign = edge.correlation > 0 ? 1 : -0.3
      const force = sign * Math.abs(edge.correlation) * 0.15
      fx[i] += force * dx / dist
      fy[i] += force * dy / dist
      fx[j] -= force * dx / dist
      fy[j] -= force * dy / dist
    }

    // Gravity
    for (let i = 0; i < n; i++) {
      fx[i] -= nodeX[i] * 0.01
      fy[i] -= nodeY[i] * 0.01
    }

    const damping = 0.7 / (1 + iter * 0.04)
    for (let i = 0; i < n; i++) {
      nodeX[i] += fx[i] * damping
      nodeY[i] += fy[i] * damping
    }
  }

  return { x: nodeX, y: nodeY }
}

function getLayout(nodes, edges) {
  if (layoutMode.value === 'circle') return layoutCircle(nodes.length)
  if (layoutMode.value === 'radial') return layoutRadial(nodes, edges)
  if (layoutMode.value === 'organic') return layoutOrganic(nodes, edges)
  return layoutForceDirected(nodes, edges)
}

// --- Rendering ---

async function renderNetwork() {
  if (!networkData.value || !networkChartEl.value) return

  await ensurePlotly()
  const c = chartColors()
  const { nodes, edges } = networkData.value

  if (!nodes.length) return

  // Compute layout
  const { x: nodeX, y: nodeY } = getLayout(nodes, edges)

  // Build id→index mapping
  const idxMap = {}
  nodes.forEach((nd, i) => { idxMap[nd.id] = i })

  // Edge traces
  const edgeTraces = []
  for (const edge of edges) {
    const i = idxMap[edge.source]
    const j = idxMap[edge.target]
    if (i === undefined || j === undefined) continue

    const isPositive = edge.correlation > 0
    edgeTraces.push({
      type: 'scatter',
      mode: 'lines',
      x: [nodeX[i], nodeX[j], null],
      y: [nodeY[i], nodeY[j], null],
      line: {
        color: isPositive
          ? `rgba(150, 150, 150, ${highlightedModule.value !== null ? 0.1 : 0.3})`
          : `rgba(200, 80, 80, ${highlightedModule.value !== null ? 0.1 : 0.35})`,
        width: Math.min(4, 0.5 + Math.abs(edge.correlation) * 3),
        dash: isPositive ? 'solid' : 'dash',
      },
      hoverinfo: 'skip',
      showlegend: false,
    })
  }

  // Node colors by mode
  const nodeColors = nodes.map(nd => {
    if (highlightedModule.value !== null && nd.module !== highlightedModule.value) {
      return c.dimmed
    }
    if (colorMode.value === 'taxonomy') {
      return nd.color
    } else if (colorMode.value === 'module') {
      return MODULE_COLORS[nd.module % MODULE_COLORS.length]
    } else {
      // enrichment
      return nd.enriched_class === 1 ? c.class1 : c.class0
    }
  })

  // Node sizes: by degree (scaled)
  const maxDegree = Math.max(1, ...nodes.map(n => n.degree))
  const nodeSizes = nodes.map(nd => 8 + (nd.degree / maxDegree) * 22)

  // Node symbols: square for enriched_class 1, circle for 0
  const nodeSymbols = nodes.map(nd => {
    if (fbmOverlay.value && nd.fbm_coefficient != null) {
      return nd.fbm_coefficient > 0 ? 'diamond' : nd.fbm_coefficient < 0 ? 'square' : 'circle'
    }
    return nd.enriched_class === 1 ? 'square' : 'circle'
  })

  // Node opacity
  const nodeOpacity = nodes.map(nd => {
    if (highlightedModule.value !== null && nd.module !== highlightedModule.value) return 0.2
    return 0.9
  })

  // Build hover text
  const hoverTexts = nodes.map(nd => {
    let text = `<b>${nd.species || nd.id}</b><br>`
    text += `${nd.phylum} / ${nd.family}<br>`
    text += `Degree: ${nd.degree}<br>`
    text += `Module: ${nd.module + 1}<br>`
    text += `Betweenness: ${nd.betweenness}<br>`
    text += `Prev(0): ${(nd.prevalence_0 * 100).toFixed(1)}% | Prev(1): ${(nd.prevalence_1 * 100).toFixed(1)}%`
    if (fbmOverlay.value && nd.fbm_prevalence != null) {
      text += `<br>FBM prev: ${(nd.fbm_prevalence * 100).toFixed(1)}%`
      text += ` | coeff: ${nd.fbm_coefficient > 0 ? '+1' : nd.fbm_coefficient < 0 ? '-1' : '0'}`
    }
    return text
  })

  // Node border: highlight FBM nodes
  const nodeBorderWidth = nodes.map(nd => {
    if (fbmOverlay.value && nd.fbm_prevalence != null) return 2.5
    return 1
  })
  const nodeBorderColor = nodes.map(nd => {
    if (fbmOverlay.value && nd.fbm_prevalence != null) {
      return nd.fbm_coefficient > 0 ? c.class1 : nd.fbm_coefficient < 0 ? c.class0 : c.text
    }
    return c.text
  })

  const nodeTrace = {
    type: 'scatter',
    mode: 'markers+text',
    x: nodeX,
    y: nodeY,
    text: nodes.map(nd => {
      // Short label: first letter + species
      const sp = nd.species || nd.id
      if (sp.length > 20) return sp.substring(0, 18) + '..'
      return sp
    }),
    textposition: 'top center',
    textfont: { color: c.text, size: 8 },
    marker: {
      size: nodeSizes,
      color: nodeColors,
      symbol: nodeSymbols,
      opacity: nodeOpacity,
      line: { color: nodeBorderColor, width: nodeBorderWidth },
    },
    hovertemplate: '%{customdata}<extra></extra>',
    customdata: hoverTexts,
    showlegend: false,
  }

  const layout = chartLayout({
    xaxis: { visible: false, showgrid: false, zeroline: false },
    yaxis: { visible: false, showgrid: false, zeroline: false, scaleanchor: 'x' },
    height: 600,
    margin: { t: 10, b: 10, l: 10, r: 10 },
    hovermode: 'closest',
  })

  Plotly.newPlot(networkChartEl.value, [...edgeTraces, nodeTrace], layout, {
    responsive: true,
    displayModeBar: false,
  })
}

// Watchers
watch([prevalenceThreshold, correlationThreshold, classFilter, fbmOverlay], debouncedFetch)
watch([colorMode, layoutMode, highlightedModule], () => {
  if (networkData.value) renderNetwork()
})

watch(() => props.active, (active) => {
  if (active && !networkData.value) fetchNetwork()
})

onMounted(() => {
  if (props.active) fetchNetwork()
})
</script>

<style scoped>
.ecosystem-tab {
  padding: 0.5rem 0;
}

.eco-controls {
  margin-bottom: 1rem;
}

.eco-controls-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: center;
}

.eco-control {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  color: var(--text-secondary, #666);
}

.eco-control input[type="range"] {
  width: 100px;
}

.eco-control select {
  padding: 0.2rem 0.4rem;
  border: 1px solid var(--border, #ddd);
  border-radius: 4px;
  background: var(--bg-surface, #fff);
  color: var(--text, #333);
  font-size: 0.82rem;
}

.eco-value {
  font-weight: 600;
  min-width: 3rem;
  text-align: right;
  font-size: 0.85rem;
}

.eco-chart-wrap {
  border: 1px solid var(--border, #ddd);
  border-radius: 8px;
  overflow: hidden;
}

.eco-chart {
  width: 100%;
  min-height: 600px;
}

.eco-stats-bar {
  display: flex;
  gap: 1.5rem;
  padding: 0.6rem 1rem;
  font-size: 0.85rem;
  color: var(--text-secondary, #666);
  border: 1px solid var(--border, #ddd);
  border-top: none;
  border-radius: 0 0 8px 8px;
  background: var(--bg-surface-alt, #fafafa);
}

.eco-bottom {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 1rem;
  margin-top: 1rem;
}

.eco-modules h4,
.eco-legend h4 {
  font-size: 0.9rem;
  margin: 0 0 0.5rem;
}

.eco-module-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.5rem;
  border-radius: 4px;
  font-size: 0.82rem;
  cursor: pointer;
  transition: background 0.15s;
}

.eco-module-item:hover {
  background: var(--bg-hover, #f0f0f0);
}

.eco-module-item.highlighted {
  background: var(--bg-active, #e0e8f0);
  font-weight: 600;
}

.eco-module-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.eco-module-size {
  color: var(--text-secondary, #999);
  font-size: 0.78rem;
}

.eco-module-phylum {
  color: var(--text-secondary, #999);
  font-size: 0.78rem;
  font-style: italic;
  margin-left: auto;
}

.eco-legend-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 1rem;
}

.eco-legend-item {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.78rem;
}

.eco-legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.eco-legend-family {
  font-weight: 500;
}

.eco-legend-phylum {
  color: var(--text-secondary, #999);
  font-style: italic;
}

.loading {
  text-align: center;
  padding: 3rem;
  color: var(--text-secondary, #999);
}

.error-text {
  color: var(--danger, #e53935);
  padding: 1rem;
  text-align: center;
}

@media (max-width: 768px) {
  .eco-bottom {
    grid-template-columns: 1fr;
  }
  .eco-controls-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
