<template>
  <div class="project-detail" v-if="project">
    <div class="header">
      <h2>{{ project.name }}</h2>
      <router-link
        :to="`/project/${project.project_id}/run`"
        class="btn btn-primary"
        v-if="project.datasets.length > 0"
      >
        Run Analysis
      </router-link>
    </div>

    <!-- Dataset Upload -->
    <section class="section">
      <h3>Datasets</h3>
      <div class="upload-area">
        <label>
          <strong>Upload X (features) file:</strong>
          <input type="file" accept=".tsv,.csv,.txt" @change="e => uploadFile(e, 'X')" />
        </label>
        <label>
          <strong>Upload y (labels) file:</strong>
          <input type="file" accept=".tsv,.csv,.txt" @change="e => uploadFile(e, 'y')" />
        </label>
      </div>
      <div v-if="project.datasets.length > 0" class="dataset-list">
        <div v-for="d in project.datasets" :key="d.id" class="dataset-item">
          {{ d.filename }} <span class="id">({{ d.id }})</span>
        </div>
      </div>
      <div v-else class="empty">No datasets uploaded yet.</div>
    </section>

    <!-- Jobs -->
    <section class="section" v-if="project.jobs.length > 0">
      <h3>Analysis Jobs</h3>
      <div v-for="j in project.jobs" :key="j" class="job-item">
        <router-link :to="`/project/${project.project_id}/results/${j}`">
          Job {{ j }}
        </router-link>
      </div>
    </section>
  </div>
  <div v-else class="loading">Loading project...</div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const project = ref(null)
const uploadInfo = ref(null)

async function fetchProject() {
  try {
    const { data } = await axios.get(`/api/projects/${route.params.id}`)
    project.value = data
  } catch (e) {
    console.error('Failed to load project:', e)
  }
}

async function uploadFile(event, label) {
  const file = event.target.files[0]
  if (!file) return

  const formData = new FormData()
  formData.append('file', file)

  try {
    const { data } = await axios.post(
      `/api/projects/${route.params.id}/datasets`,
      formData,
      { params: { features_in_rows: true } }
    )
    uploadInfo.value = data
    await fetchProject()
  } catch (e) {
    console.error('Upload failed:', e)
  }
}

onMounted(fetchProject)
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.btn {
  padding: 0.5rem 1.5rem;
  border-radius: 6px;
  text-decoration: none;
  font-weight: 600;
}

.btn-primary {
  background: #1a1a2e;
  color: white;
}

.section {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  margin-bottom: 1.5rem;
}

.section h3 {
  margin-bottom: 1rem;
  color: #1a1a2e;
}

.upload-area {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-bottom: 1rem;
}

.upload-area label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.9rem;
}

.dataset-list {
  margin-top: 1rem;
}

.dataset-item {
  padding: 0.5rem 0;
  border-bottom: 1px solid #eceff1;
  font-size: 0.9rem;
}

.dataset-item .id {
  color: #90a4ae;
  font-size: 0.8rem;
}

.job-item {
  padding: 0.5rem 0;
}

.job-item a {
  color: #1565c0;
}

.loading, .empty {
  text-align: center;
  padding: 2rem;
  color: #90a4ae;
}
</style>
