<template>
  <div class="projects">
    <h2>Projects</h2>

    <div class="create-form">
      <input
        v-model="newName"
        placeholder="New project name..."
        @keyup.enter="createProject"
      />
      <button @click="createProject" :disabled="!newName.trim()">
        Create Project
      </button>
    </div>

    <div v-if="loading" class="loading">Loading...</div>

    <div v-if="availableSamples.length > 0" class="samples-section">
      <h3>Demo Datasets</h3>
      <div v-for="s in availableSamples" :key="s.id" class="sample-card">
        <div>
          <strong>{{ s.name }}</strong>
          <p class="sample-desc">{{ s.description }}</p>
        </div>
        <span v-if="s.loaded" class="sample-loaded">Already loaded</span>
        <button v-else @click="loadSample(s.id)" :disabled="loadingSample">
          {{ loadingSample ? 'Loading...' : 'Load Demo' }}
        </button>
      </div>
    </div>

    <div v-if="!loading && projects.length === 0" class="empty">
      No projects yet. Create one above or load the demo.
    </div>

    <div v-if="projects.length > 0" class="project-list">
      <div
        v-for="p in projects"
        :key="p.project_id"
        class="project-card"
        @click="$router.push(`/project/${p.project_id}`)"
      >
        <div class="card-content">
          <h3>{{ p.name }}</h3>
          <div class="meta">
            <span>{{ p.datasets.length }} datasets</span>
            <span>{{ p.jobs.length }} jobs</span>
            <span>{{ formatDate(p.created_at) }}</span>
          </div>
        </div>
        <button class="delete-btn" @click.stop="deleteProject(p.project_id, p.name)" title="Delete project">&times;</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()

const projects = ref([])
const newName = ref('')
const loading = ref(true)
const samples = ref([])
const loadingSample = ref(false)

const projectNames = computed(() => new Set(projects.value.map(p => p.name)))
const availableSamples = computed(() =>
  samples.value.map(s => ({ ...s, loaded: projectNames.value.has(s.name) }))
)

async function fetchProjects() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/projects/')
    projects.value = data
  } catch (e) {
    console.error('Failed to load projects:', e)
  } finally {
    loading.value = false
  }
}

async function fetchSamples() {
  try {
    const { data } = await axios.get('/api/samples/')
    samples.value = data.filter(s => s.available)
  } catch (e) {
    console.error('Failed to load samples:', e)
  }
}

async function loadSample(sampleId) {
  loadingSample.value = true
  try {
    const { data } = await axios.post(`/api/samples/${sampleId}/load`)
    router.push(`/project/${data.project_id}`)
  } catch (e) {
    console.error('Failed to load sample:', e)
  } finally {
    loadingSample.value = false
  }
}

async function createProject() {
  if (!newName.value.trim()) return
  try {
    await axios.post('/api/projects/', null, { params: { name: newName.value.trim() } })
    newName.value = ''
    await fetchProjects()
  } catch (e) {
    console.error('Failed to create project:', e)
  }
}

async function deleteProject(id, name) {
  if (!confirm(`Delete project "${name}"? This cannot be undone.`)) return
  try {
    await axios.delete(`/api/projects/${id}`)
    await fetchProjects()
  } catch (e) {
    console.error('Failed to delete project:', e)
    alert('Delete failed: ' + (e.response?.data?.detail || e.message))
  }
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString()
}

onMounted(() => {
  fetchProjects()
  fetchSamples()
})
</script>

<style scoped>
.projects h2 {
  margin-bottom: 1.5rem;
}

.create-form {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 2rem;
}

.create-form input {
  flex: 1;
  padding: 0.5rem 1rem;
  border: 1px solid #cfd8dc;
  border-radius: 6px;
  font-size: 0.9rem;
}

.create-form button {
  padding: 0.5rem 1.5rem;
  background: #1a1a2e;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}

.create-form button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.project-list {
  display: grid;
  gap: 1rem;
}

.project-card {
  display: flex;
  align-items: center;
  background: white;
  padding: 1.25rem;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  cursor: pointer;
  transition: box-shadow 0.2s;
}

.project-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

.card-content {
  flex: 1;
}

.card-content h3 {
  margin-bottom: 0.5rem;
}

.delete-btn {
  background: none;
  border: none;
  font-size: 1.4rem;
  color: #b0bec5;
  cursor: pointer;
  padding: 0 0.5rem;
  line-height: 1;
  flex-shrink: 0;
}

.delete-btn:hover {
  color: #e53935;
}

.meta {
  display: flex;
  gap: 1.5rem;
  font-size: 0.85rem;
  color: #78909c;
}

.samples-section {
  margin-bottom: 2rem;
}

.samples-section h3 {
  font-size: 0.95rem;
  color: #546e7a;
  margin-bottom: 0.75rem;
}

.sample-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #e8f5e9;
  padding: 1rem 1.25rem;
  border-radius: 8px;
  margin-bottom: 0.5rem;
}

.sample-desc {
  font-size: 0.82rem;
  color: #546e7a;
  margin-top: 0.25rem;
}

.sample-card button {
  padding: 0.4rem 1rem;
  background: #2e7d32;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  white-space: nowrap;
}

.sample-card button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.sample-loaded {
  font-size: 0.82rem;
  color: #4caf50;
  font-weight: 500;
  white-space: nowrap;
}

.loading, .empty {
  text-align: center;
  padding: 3rem;
  color: #90a4ae;
}
</style>
