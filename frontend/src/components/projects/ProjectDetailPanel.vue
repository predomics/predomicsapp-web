<template>
  <div class="detail-panel" v-if="project">
    <!-- Header -->
    <div class="detail-header">
      <div class="header-info">
        <h2>{{ project.name }}</h2>
        <p v-if="project.description" class="desc">{{ project.description }}</p>
        <div class="dates">
          <span>Created {{ formatDate(project.created_at) }}</span>
          <span v-if="project.updated_at"> &middot; Modified {{ relativeDate(project.updated_at) }}</span>
        </div>
      </div>
      <div class="header-actions">
        <button class="btn btn-primary" @click="$emit('open', project.project_id)">Open Project</button>
        <button class="btn btn-outline" @click="$emit('share', project.project_id)">Share</button>
        <button class="btn btn-danger-outline" @click="$emit('delete', project)">Delete</button>
      </div>
    </div>

    <!-- Stat badges row -->
    <div class="stat-row">
      <div class="stat badge-dataset">
        <span class="stat-num">{{ project.datasets?.length || 0 }}</span>
        <span class="stat-label">Datasets</span>
      </div>
      <div class="stat badge-job">
        <span class="stat-num">{{ project.job_count || project.jobs?.length || 0 }}</span>
        <span class="stat-label">Jobs</span>
      </div>
      <div class="stat badge-share">
        <span class="stat-num">{{ project.share_count || 0 }}</span>
        <span class="stat-label">Shared</span>
      </div>
    </div>

    <!-- Datasets section -->
    <section v-if="project.datasets?.length > 0" class="detail-section">
      <h3>Datasets</h3>
      <div v-for="ds in project.datasets" :key="ds.id" class="ds-group-card">
        <div class="ds-group-name">{{ ds.name }}</div>
        <div class="ds-files">
          <span v-for="f in ds.files" :key="f.id" class="file-chip" :class="f.role">
            {{ f.filename }}
            <span v-if="f.role" class="file-role">{{ f.role }}</span>
          </span>
        </div>
      </div>
    </section>

    <!-- Recent Jobs section -->
    <section v-if="project.jobs?.length > 0" class="detail-section">
      <h3>Recent Jobs</h3>
      <div class="job-list">
        <div v-for="jobId in project.jobs.slice(0, 5)" :key="jobId" class="job-row">
          <span class="job-id">{{ jobId.slice(0, 8) }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
defineProps({
  project: { type: Object, default: null },
})

defineEmits(['open', 'share', 'delete'])

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

function relativeDate(iso) {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 30) return `${days}d ago`
  return formatDate(iso)
}
</script>

<style scoped>
.detail-panel {
  padding: 1.5rem;
  height: 100%;
  overflow-y: auto;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.header-info h2 {
  font-size: 1.4rem;
  color: var(--text-primary);
  margin: 0 0 0.25rem;
}

.desc {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-bottom: 0.25rem;
}

.dates {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.header-actions {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
}

.btn {
  padding: 0.4rem 1rem;
  border-radius: 6px;
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  border: 1.5px solid transparent;
  transition: all 0.15s;
}

.btn-primary {
  background: var(--accent);
  color: var(--accent-text);
}

.btn-primary:hover { opacity: 0.9; }

.btn-outline {
  background: transparent;
  border-color: var(--border);
  color: var(--text-secondary);
}

.btn-outline:hover {
  border-color: var(--text-secondary);
  color: var(--text-primary);
}

.btn-danger-outline {
  background: transparent;
  border-color: var(--border);
  color: var(--text-muted);
}

.btn-danger-outline:hover {
  border-color: var(--danger);
  color: var(--danger);
}

/* Stat row */
.stat-row {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.75rem 1.25rem;
  border-radius: 10px;
  min-width: 80px;
}

.stat.badge-dataset { background: var(--badge-dataset, #e3f2fd); }
.stat.badge-job { background: var(--badge-job, #f3e5f5); }
.stat.badge-share { background: var(--badge-share, #e8f5e9); }

.stat-num {
  font-size: 1.3rem;
  font-weight: 700;
  line-height: 1;
}

.stat.badge-dataset .stat-num { color: var(--badge-dataset-text, #1565c0); }
.stat.badge-job .stat-num { color: var(--badge-job-text, #7b1fa2); }
.stat.badge-share .stat-num { color: var(--badge-share-text, #2e7d32); }

.stat-label {
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-top: 0.2rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

/* Sections */
.detail-section {
  margin-bottom: 1.5rem;
}

.detail-section h3 {
  font-size: 0.9rem;
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
  font-weight: 600;
}

/* Dataset group cards */
.ds-group-card {
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  margin-bottom: 0.5rem;
}

.ds-group-name {
  font-weight: 600;
  font-size: 0.85rem;
  color: var(--text-primary);
  margin-bottom: 0.4rem;
}

.ds-files {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.file-chip {
  font-size: 0.72rem;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  background: var(--bg-badge);
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}

.file-role {
  font-size: 0.65rem;
  padding: 0 0.25rem;
  border-radius: 3px;
  background: var(--badge-dataset, #e3f2fd);
  color: var(--badge-dataset-text, #1565c0);
  font-weight: 600;
  text-transform: uppercase;
}

/* Job list */
.job-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.4rem 0;
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.job-id {
  font-family: monospace;
  font-size: 0.78rem;
  color: var(--text-muted);
}
</style>
