import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export const useProjectStore = defineStore('project', () => {
  const projects = ref([])
  const sharedProjects = ref([])
  const current = ref(null)
  const selectedId = ref(null)
  const activeJobId = ref(null)
  const showConsole = ref(false)
  const dataFilters = ref({
    std_threshold: null,
    prevalence_min_pct: 10,
    top_n_significant: null,
    method: 'wilcoxon',
  })

  async function fetchAll(includeArchived = false) {
    const { data } = await axios.get('/api/projects/', {
      params: { include_archived: includeArchived },
    })
    projects.value = data
  }

  async function fetchSharedProjects() {
    try {
      const { data } = await axios.get('/api/projects/shared-with-me')
      sharedProjects.value = data
    } catch { /* ignore */ }
  }

  async function fetchOne(id) {
    const { data } = await axios.get(`/api/projects/${id}`)
    current.value = data
    return data
  }

  async function create(name, description = '') {
    const { data } = await axios.post('/api/projects/', null, { params: { name, description } })
    await fetchAll()
    return data
  }

  async function updateProject(id, { name, description, class_names } = {}) {
    const body = {}
    if (name !== undefined) body.name = name
    if (description !== undefined) body.description = description
    if (class_names !== undefined) body.class_names = class_names
    const { data } = await axios.patch(`/api/projects/${id}`, body)
    const idx = projects.value.findIndex(p => p.project_id === id)
    if (idx >= 0) projects.value[idx] = data
    if (current.value?.project_id === id) current.value = data
    return data
  }

  async function remove(id) {
    await axios.delete(`/api/projects/${id}`)
    if (selectedId.value === id) selectedId.value = null
    await fetchAll()
  }

  async function archiveProject(id) {
    const { data } = await axios.post(`/api/projects/${id}/archive`)
    const idx = projects.value.findIndex(p => p.project_id === id)
    if (idx >= 0) projects.value[idx] = data
    return data
  }

  function startJob(jobId) {
    activeJobId.value = jobId
    showConsole.value = true
  }

  function closeConsole() {
    showConsole.value = false
  }

  return {
    projects, sharedProjects, current, selectedId,
    activeJobId, showConsole, dataFilters,
    fetchAll, fetchSharedProjects, fetchOne, create, updateProject, remove,
    archiveProject, startJob, closeConsole,
  }
})
