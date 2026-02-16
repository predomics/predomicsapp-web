<template>
  <div class="console-panel">
    <div class="console-header">
      <h4>Console Output</h4>
      <span class="status-badge" :class="jobStatus">{{ jobStatus }}</span>
      <template v-if="progress.generation > 0 && jobStatus === 'running'">
        <div class="progress-info">
          <span class="progress-gen">Gen {{ progress.generation }}<template v-if="progress.maxGen"> / {{ progress.maxGen }}</template></span>
          <span class="progress-k" v-if="progress.k">k={{ progress.k }}</span>
          <span class="progress-lang" v-if="progress.language">{{ progress.language }}</span>
          <span class="progress-eta" v-if="etaDisplay">{{ etaDisplay }}</span>
        </div>
        <div class="progress-bar-wrap" v-if="progress.maxGen">
          <div class="progress-bar" :style="{ width: progressPct + '%' }"></div>
        </div>
      </template>
      <button class="btn-toggle-chart" v-if="progressPoints.length >= 2" @click="showChart = !showChart" :title="showChart ? 'Hide chart' : 'Show live chart'">
        <svg width="14" height="14" viewBox="0 0 14 14"><path d="M1 12 L4 7 L7 9 L10 3 L13 5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
      <button class="close-btn" @click="$emit('close')" title="Minimize console">&#9660;</button>
    </div>

    <!-- Live sparkline charts -->
    <div v-if="showChart && progressPoints.length >= 2" class="chart-strip">
      <svg :viewBox="`0 0 ${chartW} ${chartH}`" class="sparkline-svg" preserveAspectRatio="none">
        <!-- Grid lines -->
        <line x1="0" :y1="chartH * 0.25" :x2="chartW" :y2="chartH * 0.25" stroke="rgba(255,255,255,0.06)" stroke-width="0.5" />
        <line x1="0" :y1="chartH * 0.5" :x2="chartW" :y2="chartH * 0.5" stroke="rgba(255,255,255,0.06)" stroke-width="0.5" />
        <line x1="0" :y1="chartH * 0.75" :x2="chartW" :y2="chartH * 0.75" stroke="rgba(255,255,255,0.06)" stroke-width="0.5" />
        <!-- Generation line (cyan) -->
        <polyline :points="genPath" fill="none" stroke="#00BFFF" stroke-width="1.5" stroke-linejoin="round" />
        <!-- k line (green) -->
        <polyline :points="kPath" fill="none" stroke="#98c379" stroke-width="1.5" stroke-linejoin="round" stroke-dasharray="3,2" />
      </svg>
      <div class="chart-legend">
        <span class="legend-gen">&#9644; Generation</span>
        <span class="legend-k">&#9644; k (features)</span>
        <span class="legend-max" v-if="progress.maxGen">max={{ progress.maxGen }}</span>
      </div>
    </div>

    <div class="console" ref="consoleEl">
      <pre v-html="renderedLog"></pre>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const props = defineProps({
  projectId: { type: String, required: true },
  jobId: { type: String, required: true },
})

const emit = defineEmits(['close', 'completed', 'failed', 'progress'])

const logContent = ref('')
const jobStatus = ref('pending')
const consoleEl = ref(null)
const progress = ref({ generation: 0, maxGen: 0, k: 0, language: '' })
const progressPoints = ref([])
const showChart = ref(true)
let pollTimer = null
let ws = null
let wsConnected = false

let errorCount = 0
let startTime = null  // When we first see generation > 0

/* ── Sparkline chart ─────────────────────────────────── */
const chartW = 300
const chartH = 60

function buildPath(points, key, maxVal) {
  if (points.length < 2 || maxVal <= 0) return ''
  const xStep = chartW / (points.length - 1)
  return points.map((p, i) => {
    const x = i * xStep
    const y = chartH - (p[key] / maxVal) * (chartH - 4) - 2
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}

const genPath = computed(() => {
  const pts = progressPoints.value
  const maxGen = progress.value.maxGen || Math.max(...pts.map(p => p.generation), 1)
  return buildPath(pts, 'generation', maxGen)
})

const kPath = computed(() => {
  const pts = progressPoints.value
  const maxK = Math.max(...pts.map(p => p.k), 1)
  return buildPath(pts, 'k', maxK)
})

/* ── Progress parser ─────────────────────────────────── */
// Parses generation lines like: "#42      | best: Ternary:Prevalence  \t0 ████ 1 [k=55, age=0]"
const GEN_RE = /#(\d+)\s+\|\s+best:\s+(\S+)/
const K_RE = /\[k=(\d+)/

function parseProgress(text) {
  if (!text) return
  // Find the last generation line
  const lines = text.split('\n')
  let lastGen = 0, lastK = 0, lastLang = ''
  for (let i = lines.length - 1; i >= 0; i--) {
    const clean = lines[i].replace(/\x1b\[[0-9;]*m/g, '')
    const gm = clean.match(GEN_RE)
    if (gm) {
      lastGen = parseInt(gm[1])
      lastLang = gm[2]
      const km = clean.match(K_RE)
      if (km) lastK = parseInt(km[1])
      break
    }
  }
  if (lastGen > 0) {
    progress.value.generation = lastGen
    progress.value.k = lastK
    progress.value.language = lastLang
    // Start time tracking on first generation seen
    if (!startTime) startTime = Date.now()
  }
  // Try to extract maxGen from early lines (config echo)
  if (!progress.value.maxGen) {
    for (const line of lines.slice(0, 50)) {
      const clean = line.replace(/\x1b\[[0-9;]*m/g, '')
      // Look for max_epochs in config output
      const em = clean.match(/max_epochs[:\s]+(\d+)/i)
      if (em) { progress.value.maxGen = parseInt(em[1]); break }
    }
  }
  // Emit progress data to parent for minimized bar display
  emitProgress()
}

/* ── Handle structured progress from backend ─────────── */
function handleProgressData(data) {
  if (data.max_gen) progress.value.maxGen = data.max_gen
  if (data.points?.length > 0) {
    progressPoints.value = data.points
    const last = data.points[data.points.length - 1]
    progress.value.generation = last.generation
    progress.value.k = last.k
    progress.value.language = last.language
    if (!startTime && last.generation > 0) startTime = Date.now()
    emitProgress()
  }
}

/* ── ETA calculation ─────────────────────────────────── */
const progressPct = computed(() => {
  if (!progress.value.maxGen || progress.value.generation <= 0) return 0
  return Math.min(100, (progress.value.generation / progress.value.maxGen) * 100)
})

const etaDisplay = computed(() => {
  if (!startTime || !progress.value.maxGen || progress.value.generation <= 0) return ''
  const elapsed = (Date.now() - startTime) / 1000  // seconds
  const pct = progress.value.generation / progress.value.maxGen
  if (pct >= 1) return ''
  const totalEstimate = elapsed / pct
  const remaining = Math.max(0, totalEstimate - elapsed)
  return formatEta(remaining)
})

function formatEta(seconds) {
  if (seconds < 60) return `~${Math.ceil(seconds)}s left`
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60)
    const s = Math.ceil(seconds % 60)
    return `~${m}m ${s}s left`
  }
  const h = Math.floor(seconds / 3600)
  const m = Math.ceil((seconds % 3600) / 60)
  return `~${h}h ${m}m left`
}

function emitProgress() {
  emit('progress', {
    generation: progress.value.generation,
    maxGen: progress.value.maxGen,
    k: progress.value.k,
    language: progress.value.language,
    pct: progressPct.value,
    eta: etaDisplay.value,
    status: jobStatus.value,
  })
}

/* ── ANSI → HTML converter ───────────────────────────── */
const ANSI_COLORS = {
  30: '#4a4a4a', 31: '#e06c75', 32: '#98c379', 33: '#e5c07b',
  34: '#61afef', 35: '#c678dd', 36: '#56b6c2', 37: '#dcdfe4',
  90: '#7f848e', 91: '#e06c75', 92: '#98c379', 93: '#e5c07b',
  94: '#61afef', 95: '#c678dd', 96: '#56b6c2', 97: '#ffffff',
}

function ansiToHtml(text) {
  if (!text) return 'Waiting for output...'
  // Escape HTML first
  let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  // Replace ANSI escape sequences
  html = html.replace(/\x1b\[([0-9;]*)m/g, (_, codes) => {
    if (!codes || codes === '0') return '</span>'
    const parts = codes.split(';')
    const styles = []
    for (const code of parts) {
      const n = parseInt(code, 10)
      if (n === 1) styles.push('font-weight:bold')
      else if (n === 3) styles.push('font-style:italic')
      else if (n === 4) styles.push('text-decoration:underline')
      else if (ANSI_COLORS[n]) styles.push(`color:${ANSI_COLORS[n]}`)
    }
    return styles.length ? `<span style="${styles.join(';')}">` : ''
  })
  return html
}

const renderedLog = computed(() => ansiToHtml(logContent.value))

/* ── Fetch max epochs from job config ─────────────────── */
async function fetchMaxEpochs() {
  try {
    const { data } = await axios.get(`/api/analysis/${props.projectId}/jobs/${props.jobId}`)
    const epMatch = data.config_summary?.match(/ep=(\d+)/)
    if (epMatch) {
      progress.value.maxGen = parseInt(epMatch[1])
    }
  } catch { /* ignore */ }
}

/* ── WebSocket ───────────────────────────────────────── */
function getWsUrl() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${location.host}/ws/jobs/${props.projectId}/${props.jobId}?token=${auth.token}`
}

function connectWebSocket() {
  if (!auth.token) { startPolling(); return }
  try {
    ws = new WebSocket(getWsUrl())

    ws.onopen = () => {
      wsConnected = true
      stopPolling()  // WS is live, stop HTTP polling
    }

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'log') {
        logContent.value += msg.content
        parseProgress(logContent.value)
        nextTick(() => {
          if (consoleEl.value) consoleEl.value.scrollTop = consoleEl.value.scrollHeight
        })
      } else if (msg.type === 'status') {
        jobStatus.value = msg.status
      } else if (msg.type === 'progress') {
        handleProgressData(msg.data)
      } else if (msg.type === 'done') {
        jobStatus.value = msg.status
        if (msg.status === 'completed') emit('completed', props.jobId)
        else if (msg.status === 'failed') emit('failed', props.jobId)
        closeWebSocket()
      }
    }

    ws.onerror = () => {
      closeWebSocket()
      if (!wsConnected) startPolling()  // WS never connected, fall back
    }

    ws.onclose = () => {
      ws = null
      if (wsConnected && (jobStatus.value === 'running' || jobStatus.value === 'pending')) {
        wsConnected = false
        startPolling()  // Unexpected close, fall back to polling
      }
    }
  } catch {
    startPolling()
  }
}

function closeWebSocket() {
  if (ws) { try { ws.close() } catch { /* ignore */ } ws = null }
}

/* ── HTTP Polling (fallback) ─────────────────────────── */
async function pollLogs() {
  try {
    const { data } = await axios.get(`/api/analysis/${props.projectId}/jobs/${props.jobId}/logs`)
    errorCount = 0
    logContent.value = data.log
    jobStatus.value = data.status
    parseProgress(data.log)

    await nextTick()
    if (consoleEl.value) {
      consoleEl.value.scrollTop = consoleEl.value.scrollHeight
    }

    if (data.status === 'completed') {
      stopPolling()
      emit('completed', props.jobId)
    } else if (data.status === 'failed') {
      stopPolling()
      emit('failed', props.jobId)
    }
  } catch (e) {
    errorCount++
    if (errorCount >= 10) {
      logContent.value = '[error] Job not found. Close the console and re-launch the analysis.'
      jobStatus.value = 'failed'
      stopPolling()
      emit('failed', props.jobId)
    }
  }
}

async function pollProgress() {
  try {
    const { data } = await axios.get(`/api/analysis/${props.projectId}/jobs/${props.jobId}/progress`)
    if (data.points?.length > 0) handleProgressData(data)
  } catch { /* ignore */ }
}

function startPolling() {
  if (pollTimer) return  // Already polling
  fetchMaxEpochs()
  pollLogs()
  pollProgress()
  pollTimer = setInterval(() => { pollLogs(); pollProgress() }, 1000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

/* ── Lifecycle ───────────────────────────────────────── */
function startConsole() {
  fetchMaxEpochs()
  connectWebSocket()
  // Start polling as initial fallback; will be stopped if WS connects
  startPolling()
}

function stopConsole() {
  stopPolling()
  closeWebSocket()
  wsConnected = false
}

watch(() => props.jobId, (newId) => {
  if (newId) {
    logContent.value = ''
    jobStatus.value = 'pending'
    progress.value = { generation: 0, maxGen: 0, k: 0, language: '' }
    progressPoints.value = []
    startTime = null
    stopConsole()
    startConsole()
  }
})

onMounted(startConsole)
onUnmounted(stopConsole)
</script>

<style scoped>
.console-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--console-bg);
  color: var(--console-text);
}

.console-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid var(--console-border);
  flex-shrink: 0;
}

.console-header h4 {
  margin: 0;
  font-size: 0.8rem;
  color: var(--text-nav-link);
  flex: 1;
}

.status-badge {
  padding: 0.1rem 0.4rem;
  border-radius: 8px;
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
}

.status-badge.pending { background: var(--warning-bg); color: var(--warning-dark); }
.status-badge.running { background: var(--info-bg); color: var(--info); }
.status-badge.completed { background: var(--success-bg); color: var(--success-dark); }
.status-badge.failed { background: var(--danger-bg); color: var(--danger-dark); }

.close-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 0.9rem;
  cursor: pointer;
  padding: 0 0.25rem;
  line-height: 1;
}

.close-btn:hover { color: var(--console-text); }

.btn-toggle-chart {
  background: none;
  border: 1px solid rgba(255,255,255,0.15);
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.15rem 0.3rem;
  border-radius: 4px;
  display: flex;
  align-items: center;
  transition: all 0.15s;
}
.btn-toggle-chart:hover {
  border-color: #00BFFF;
  color: #00BFFF;
}

/* Progress indicators */
.progress-info {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  font-size: 0.72rem;
  color: var(--text-nav-link);
}
.progress-gen {
  font-weight: 600;
  color: #00BFFF;
}
.progress-k {
  color: #98c379;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
}
.progress-lang {
  color: var(--text-muted);
  font-size: 0.68rem;
}
.progress-eta {
  color: #e5c07b;
  font-size: 0.68rem;
  font-style: italic;
}
.progress-bar-wrap {
  width: 80px;
  height: 6px;
  background: rgba(255,255,255,0.1);
  border-radius: 3px;
  overflow: hidden;
}
.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #00BFFF, #00e5ff);
  border-radius: 3px;
  transition: width 0.3s ease;
}

/* Live sparkline chart strip */
.chart-strip {
  padding: 0.4rem 1rem 0.25rem;
  border-bottom: 1px solid var(--console-border);
  flex-shrink: 0;
}

.sparkline-svg {
  width: 100%;
  height: 50px;
  display: block;
}

.chart-legend {
  display: flex;
  gap: 0.75rem;
  font-size: 0.62rem;
  padding-top: 0.15rem;
}
.legend-gen { color: #00BFFF; }
.legend-k { color: #98c379; }
.legend-max { color: var(--text-muted); margin-left: auto; }

.console {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem 1rem;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 0.72rem;
  line-height: 1.4;
}

.console pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
