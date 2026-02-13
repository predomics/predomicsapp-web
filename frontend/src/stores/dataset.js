import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export const useDatasetStore = defineStore('dataset', () => {
  const datasets = ref([])
  const loading = ref(false)

  async function fetchDatasets() {
    loading.value = true
    try {
      const { data } = await axios.get('/api/datasets/')
      datasets.value = data
    } finally {
      loading.value = false
    }
  }

  async function createGroup(name, description = '') {
    const { data } = await axios.post('/api/datasets/', null, {
      params: { name, description },
    })
    datasets.value.unshift(data)
    return data
  }

  async function uploadFile(datasetId, file, role = null) {
    const form = new FormData()
    form.append('file', file)
    const params = {}
    if (role) params.role = role
    const { data } = await axios.post(`/api/datasets/${datasetId}/files`, form, { params })
    const idx = datasets.value.findIndex(d => d.id === datasetId)
    if (idx >= 0) {
      datasets.value[idx].files.push(data)
    }
    return data
  }

  async function deleteFile(datasetId, fileId) {
    await axios.delete(`/api/datasets/${datasetId}/files/${fileId}`)
    const idx = datasets.value.findIndex(d => d.id === datasetId)
    if (idx >= 0) {
      datasets.value[idx].files = datasets.value[idx].files.filter(f => f.id !== fileId)
    }
  }

  async function deleteDataset(id) {
    await axios.delete(`/api/datasets/${id}`)
    datasets.value = datasets.value.filter(d => d.id !== id)
  }

  async function assignDataset(datasetId, projectId) {
    await axios.post(`/api/datasets/${datasetId}/assign/${projectId}`)
  }

  async function unassignDataset(datasetId, projectId) {
    await axios.delete(`/api/datasets/${datasetId}/assign/${projectId}`)
  }

  return {
    datasets, loading,
    fetchDatasets, createGroup, uploadFile, deleteFile,
    deleteDataset, assignDataset, unassignDataset,
  }
})
