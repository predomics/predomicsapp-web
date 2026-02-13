import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export const useProjectStore = defineStore('project', () => {
  const projects = ref([])
  const current = ref(null)

  async function fetchAll() {
    const { data } = await axios.get('/api/projects/')
    projects.value = data
  }

  async function fetchOne(id) {
    const { data } = await axios.get(`/api/projects/${id}`)
    current.value = data
    return data
  }

  async function create(name) {
    const { data } = await axios.post('/api/projects/', null, { params: { name } })
    await fetchAll()
    return data
  }

  async function remove(id) {
    await axios.delete(`/api/projects/${id}`)
    await fetchAll()
  }

  return { projects, current, fetchAll, fetchOne, create, remove }
})
