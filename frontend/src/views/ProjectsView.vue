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

    <div v-else-if="projects.length === 0" class="empty">
      No projects yet. Create one to get started.
    </div>

    <div v-else class="project-list">
      <div
        v-for="p in projects"
        :key="p.project_id"
        class="project-card"
        @click="$router.push(`/project/${p.project_id}`)"
      >
        <h3>{{ p.name }}</h3>
        <div class="meta">
          <span>{{ p.datasets.length }} datasets</span>
          <span>{{ p.jobs.length }} jobs</span>
          <span>{{ formatDate(p.created_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const projects = ref([])
const newName = ref('')
const loading = ref(true)

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

function formatDate(iso) {
  return new Date(iso).toLocaleDateString()
}

onMounted(fetchProjects)
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

.project-card h3 {
  margin-bottom: 0.5rem;
}

.meta {
  display: flex;
  gap: 1.5rem;
  font-size: 0.85rem;
  color: #78909c;
}

.loading, .empty {
  text-align: center;
  padding: 3rem;
  color: #90a4ae;
}
</style>
