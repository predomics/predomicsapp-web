<template>
  <div class="admin-page">
    <h2>User Administration</h2>

    <div v-if="loading" class="loading">Loading users...</div>
    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <table v-else class="user-table">
      <thead>
        <tr>
          <th>Email</th>
          <th>Name</th>
          <th>Active</th>
          <th>Admin</th>
          <th>Projects</th>
          <th>Datasets</th>
          <th>Created</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.id" :class="{ inactive: !u.is_active }">
          <td>{{ u.email }}</td>
          <td>{{ u.full_name || '—' }}</td>
          <td>
            <button
              class="toggle-btn"
              :class="u.is_active ? 'on' : 'off'"
              @click="toggleActive(u)"
              :disabled="u.id === currentUser.id"
            >
              {{ u.is_active ? 'Yes' : 'No' }}
            </button>
          </td>
          <td>
            <button
              class="toggle-btn"
              :class="u.is_admin ? 'on' : 'off'"
              @click="toggleAdmin(u)"
              :disabled="u.id === currentUser.id"
            >
              {{ u.is_admin ? 'Yes' : 'No' }}
            </button>
          </td>
          <td class="count">{{ u.project_count }}</td>
          <td class="count">{{ u.dataset_count }}</td>
          <td class="date">{{ new Date(u.created_at).toLocaleDateString() }}</td>
          <td>
            <button
              class="btn-delete"
              @click="deleteUser(u)"
              :disabled="u.id === currentUser.id"
            >
              Delete
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Default Parameters Section -->
    <h2 class="section-title">Default Parameters</h2>
    <p class="section-desc">These defaults are applied to all new analysis runs (users can override them).</p>

    <div v-if="defaultsLoading" class="loading">Loading defaults...</div>
    <div v-else class="defaults-grid">
      <div v-for="(field, idx) in defaultFields" :key="idx" class="default-field">
        <label :for="'df-' + idx">{{ field.label }}</label>
        <select v-if="field.options" :id="'df-' + idx" v-model="defaults[field.key]">
          <option :value="undefined">— use hardcoded —</option>
          <option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
        </select>
        <input
          v-else-if="field.type === 'number'"
          :id="'df-' + idx"
          type="number"
          v-model.number="defaults[field.key]"
          :placeholder="field.placeholder || ''"
        />
        <select v-else-if="field.type === 'boolean'" :id="'df-' + idx" v-model="defaults[field.key]">
          <option :value="undefined">— use hardcoded —</option>
          <option :value="true">Yes</option>
          <option :value="false">No</option>
        </select>
        <input
          v-else
          :id="'df-' + idx"
          type="text"
          v-model="defaults[field.key]"
          :placeholder="field.placeholder || ''"
        />
      </div>
    </div>
    <div class="defaults-actions">
      <button class="btn-save" @click="saveDefaults" :disabled="defaultsSaving">
        {{ defaultsSaving ? 'Saving...' : 'Save Defaults' }}
      </button>
      <button class="btn-reset" @click="resetDefaults">Reset All</button>
      <span v-if="defaultsSaved" class="save-ok">Saved!</span>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const currentUser = auth.user

const users = ref([])
const loading = ref(true)
const error = ref('')

// Default parameters
const defaults = reactive({})
const defaultsLoading = ref(false)
const defaultsSaving = ref(false)
const defaultsSaved = ref(false)

const defaultFields = [
  { key: 'general.algo', label: 'Algorithm', options: ['ga', 'beam', 'mcmc'] },
  { key: 'general.language', label: 'Languages', placeholder: 'bin,ter,ratio' },
  { key: 'general.data_type', label: 'Data Types', placeholder: 'raw,prev' },
  { key: 'general.fit', label: 'Fitness Function', options: ['auc', 'specificity', 'sensitivity', 'mcc', 'f1_score', 'g_mean'] },
  { key: 'general.seed', label: 'Random Seed', type: 'number', placeholder: '42' },
  { key: 'general.thread_number', label: 'Threads', type: 'number', placeholder: '4' },
  { key: 'ga.population_size', label: 'Population Size', type: 'number', placeholder: '5000' },
  { key: 'ga.max_epochs', label: 'Max Epochs', type: 'number', placeholder: '200' },
  { key: 'ga.k_min', label: 'Min Features (k)', type: 'number', placeholder: '1' },
  { key: 'ga.k_max', label: 'Max Features (k)', type: 'number', placeholder: '200' },
  { key: 'voting.vote', label: 'Enable Voting', type: 'boolean' },
  { key: 'importance.compute_importance', label: 'Compute Importance', type: 'boolean' },
  { key: 'data.holdout_ratio', label: 'Holdout Ratio', type: 'number', placeholder: '0.20' },
  { key: 'data.feature_minimal_prevalence_pct', label: 'Min Prevalence %', type: 'number', placeholder: '10' },
]

async function fetchDefaults() {
  defaultsLoading.value = true
  try {
    const { data } = await axios.get('/api/admin/defaults')
    Object.assign(defaults, data)
  } catch { /* ignore */ }
  finally { defaultsLoading.value = false }
}

async function saveDefaults() {
  defaultsSaving.value = true
  defaultsSaved.value = false
  try {
    // Strip undefined values
    const clean = {}
    for (const [k, v] of Object.entries(defaults)) {
      if (v !== undefined && v !== '' && v !== null) clean[k] = v
    }
    await axios.put('/api/admin/defaults', clean)
    // Reload to confirm
    Object.keys(defaults).forEach(k => delete defaults[k])
    Object.assign(defaults, clean)
    defaultsSaved.value = true
    setTimeout(() => { defaultsSaved.value = false }, 3000)
  } catch (e) {
    alert('Failed to save defaults: ' + (e.response?.data?.detail || e.message))
  } finally {
    defaultsSaving.value = false
  }
}

function resetDefaults() {
  if (!confirm('Reset all default parameters to hardcoded values?')) return
  Object.keys(defaults).forEach(k => delete defaults[k])
  saveDefaults()
}

async function fetchUsers() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await axios.get('/api/admin/users')
    users.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load users'
  } finally {
    loading.value = false
  }
}

async function toggleActive(u) {
  try {
    const { data } = await axios.patch(`/api/admin/users/${u.id}`, {
      is_active: !u.is_active,
    })
    Object.assign(u, data)
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to update user')
  }
}

async function toggleAdmin(u) {
  try {
    const { data } = await axios.patch(`/api/admin/users/${u.id}`, {
      is_admin: !u.is_admin,
    })
    Object.assign(u, data)
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to update user')
  }
}

async function deleteUser(u) {
  if (!confirm(`Delete user "${u.email}" and ALL their data? This cannot be undone.`)) return
  try {
    await axios.delete(`/api/admin/users/${u.id}`)
    users.value = users.value.filter(x => x.id !== u.id)
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to delete user')
  }
}

onMounted(() => {
  fetchUsers()
  fetchDefaults()
})
</script>

<style scoped>
.admin-page {
  max-width: 1100px;
  margin: 0 auto;
}

.admin-page h2 {
  margin-bottom: 1.5rem;
  color: var(--text-primary);
}

.loading, .error-msg {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted);
}

.error-msg { color: var(--danger); }

.user-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-card);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: var(--shadow);
}

.user-table th, .user-table td {
  padding: 0.6rem 0.75rem;
  text-align: left;
  font-size: 0.85rem;
  border-bottom: 1px solid var(--border-lighter);
}

.user-table th {
  background: var(--bg-badge);
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.user-table tr.inactive td {
  opacity: 0.5;
}

.count { text-align: center; }
.date { white-space: nowrap; color: var(--text-muted); }

.toggle-btn {
  padding: 0.2rem 0.5rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 500;
  background: var(--bg-input);
  color: var(--text-body);
  transition: all 0.15s;
}

.toggle-btn.on {
  background: var(--success-bg);
  color: var(--success-dark);
  border-color: var(--success);
}

.toggle-btn.off {
  background: var(--bg-input);
  color: var(--text-muted);
}

.toggle-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.btn-delete {
  padding: 0.2rem 0.5rem;
  background: transparent;
  border: 1px solid var(--danger);
  color: var(--danger);
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.78rem;
  transition: all 0.15s;
}

.btn-delete:hover {
  background: var(--danger-bg);
}

.btn-delete:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* Default Parameters Section */
.section-title {
  margin-top: 2.5rem;
  margin-bottom: 0.5rem;
}
.section-desc {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-bottom: 1rem;
}
.defaults-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}
.default-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.default-field label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-secondary);
}
.default-field input,
.default-field select {
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.85rem;
  background: var(--bg-input);
  color: var(--text-body);
}
.defaults-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}
.btn-save {
  padding: 0.4rem 1.25rem;
  background: var(--accent);
  color: var(--accent-text);
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 500;
}
.btn-save:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-reset {
  padding: 0.4rem 1rem;
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}
.btn-reset:hover { border-color: var(--text-secondary); }
.save-ok {
  font-size: 0.85rem;
  color: var(--success-dark, #2e7d32);
  font-weight: 500;
}
</style>
