<template>
  <div class="datasets">
    <h2>Dataset Library</h2>

    <!-- Create group form -->
    <div class="create-form">
      <input v-model="groupName" placeholder="Dataset group name..." class="name-input" @keyup.enter="createGroup" />
      <input v-model="groupDesc" placeholder="Description (optional)" class="desc-input" />
      <button @click="createGroup" :disabled="!groupName.trim() || creating">
        {{ creating ? 'Creating...' : 'Create Group' }}
      </button>
    </div>

    <div v-if="store.loading" class="loading">Loading...</div>

    <div v-if="!store.loading && store.datasets.length === 0" class="empty">
      No datasets yet. Create a group above, then upload files into it.
    </div>

    <div v-if="store.datasets.length > 0" class="dataset-list">
      <div v-for="d in store.datasets" :key="d.id" class="dataset-card">
        <div class="card-header">
          <div class="card-content">
            <h3>{{ d.name }}</h3>
            <p v-if="d.description" class="desc">{{ d.description }}</p>
            <div class="meta">
              <span>{{ formatDate(d.created_at) }}</span>
              <span>{{ d.files?.length || 0 }} file{{ (d.files?.length || 0) !== 1 ? 's' : '' }}</span>
              <span v-if="d.project_count > 0">{{ d.project_count }} project{{ d.project_count > 1 ? 's' : '' }}</span>
              <span v-else class="unused">Not assigned</span>
            </div>
          </div>
          <button class="delete-btn" @click="deleteDs(d)" title="Delete dataset group">&times;</button>
        </div>

        <!-- Files within group -->
        <div class="file-list" v-if="d.files?.length > 0">
          <div v-for="f in d.files" :key="f.id" class="file-row">
            <span class="file-name">{{ f.filename }}</span>
            <span v-if="f.role" class="file-role">{{ f.role }}</span>
            <button class="file-del" @click="deleteFile(d, f)" title="Remove file">&times;</button>
          </div>
        </div>

        <!-- Upload file into group -->
        <label class="upload-into">
          + Add file
          <input type="file" accept=".tsv,.csv,.txt" @change="e => addFile(e, d.id)" />
        </label>
      </div>
    </div>

    <div v-if="message" :class="['msg', msgType]">{{ message }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useDatasetStore } from '../stores/dataset'

const store = useDatasetStore()
const groupName = ref('')
const groupDesc = ref('')
const creating = ref(false)
const message = ref('')
const msgType = ref('success')

async function createGroup() {
  if (!groupName.value.trim()) return
  creating.value = true
  message.value = ''
  try {
    await store.createGroup(groupName.value.trim(), groupDesc.value.trim())
    message.value = `Created "${groupName.value.trim()}"`
    msgType.value = 'success'
    groupName.value = ''
    groupDesc.value = ''
  } catch (e) {
    message.value = e.response?.data?.detail || 'Create failed'
    msgType.value = 'error'
  } finally {
    creating.value = false
  }
}

async function addFile(event, datasetId) {
  const file = event.target.files[0]
  if (!file) return
  try {
    await store.uploadFile(datasetId, file)
    message.value = `Added ${file.name}`
    msgType.value = 'success'
  } catch (e) {
    message.value = e.response?.data?.detail || 'Upload failed'
    msgType.value = 'error'
  }
  event.target.value = ''
}

async function deleteFile(ds, f) {
  if (!confirm(`Remove "${f.filename}" from "${ds.name}"?`)) return
  try {
    await store.deleteFile(ds.id, f.id)
    message.value = `Removed ${f.filename}`
    msgType.value = 'success'
  } catch (e) {
    message.value = e.response?.data?.detail || 'Delete failed'
    msgType.value = 'error'
  }
}

async function deleteDs(d) {
  if (!confirm(`Delete "${d.name}" and all its files? This removes it from all projects.`)) return
  try {
    await store.deleteDataset(d.id)
    message.value = `Deleted ${d.name}`
    msgType.value = 'success'
  } catch (e) {
    message.value = e.response?.data?.detail || 'Delete failed'
    msgType.value = 'error'
  }
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString()
}

onMounted(() => store.fetchDatasets())
</script>

<style scoped>
.datasets h2 {
  margin-bottom: 1.5rem;
  color: var(--text-primary);
}

.create-form {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 2rem;
  align-items: center;
  flex-wrap: wrap;
}

.name-input {
  min-width: 180px;
  padding: 0.5rem 1rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.9rem;
  background: var(--bg-input);
  color: var(--text-body);
}

.desc-input {
  flex: 1;
  min-width: 200px;
  padding: 0.5rem 1rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.9rem;
  background: var(--bg-input);
  color: var(--text-body);
}

.create-form button {
  padding: 0.5rem 1.5rem;
  background: var(--accent);
  color: var(--accent-text);
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  white-space: nowrap;
}

.create-form button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.dataset-list {
  display: grid;
  gap: 1rem;
}

.dataset-card {
  background: var(--bg-card);
  border-radius: var(--card-radius, 12px);
  box-shadow: var(--card-shadow, 0 1px 3px rgba(0,0,0,0.06));
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: flex-start;
  padding: 1rem 1.25rem 0.75rem;
}

.card-content {
  flex: 1;
}

.card-content h3 {
  margin: 0 0 0.15rem;
  color: var(--text-primary);
  font-size: 1rem;
}

.desc {
  font-size: 0.82rem;
  color: var(--text-secondary);
  margin-bottom: 0.25rem;
}

.meta {
  display: flex;
  gap: 1.5rem;
  font-size: 0.82rem;
  color: var(--text-muted);
}

.unused {
  color: var(--text-faint);
}

.delete-btn {
  background: none;
  border: none;
  font-size: 1.4rem;
  color: var(--text-faint);
  cursor: pointer;
  padding: 0 0.5rem;
  line-height: 1;
  flex-shrink: 0;
}

.delete-btn:hover {
  color: var(--danger);
}

/* File list within a dataset group */
.file-list {
  padding: 0 1.25rem;
}

.file-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.3rem 0.5rem;
  font-size: 0.82rem;
  border-top: 1px solid var(--border-lighter);
}

.file-name {
  color: var(--text-body);
  flex: 1;
}

.file-role {
  font-size: 0.7rem;
  padding: 0.05rem 0.35rem;
  border-radius: 3px;
  background: var(--badge-dataset, #e3f2fd);
  color: var(--badge-dataset-text, #1565c0);
  font-weight: 600;
  text-transform: uppercase;
}

.file-del {
  background: none;
  border: none;
  color: var(--text-faint);
  cursor: pointer;
  font-size: 1rem;
  padding: 0;
  line-height: 1;
}

.file-del:hover { color: var(--danger); }

.upload-into {
  display: block;
  padding: 0.5rem 1.25rem;
  font-size: 0.78rem;
  color: var(--text-muted);
  cursor: pointer;
  border-top: 1px solid var(--border-lighter);
  transition: background 0.15s;
}

.upload-into:hover {
  background: var(--bg-card-hover);
  color: var(--text-secondary);
}

.upload-into input[type="file"] { display: none; }

.msg {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  border-radius: 6px;
  font-size: 0.85rem;
}

.msg.success {
  background: var(--success-bg);
  color: var(--success-dark);
}

.msg.error {
  background: var(--danger-bg);
  color: var(--danger-dark);
}

.loading, .empty {
  text-align: center;
  padding: 3rem;
  color: var(--text-faint);
}
</style>
