<template>
  <div class="home">
    <div class="hero">
      <h1>PredomicsApp</h1>
      <p class="subtitle">
        Discover sparse, interpretable predictive models from omics data.
      </p>
      <p class="description">
        Powered by <strong>gpredomics</strong> — a high-performance Rust engine
        for Binary, Ternary, and Ratio model languages using genetic algorithms,
        beam search, and Bayesian MCMC.
      </p>
      <router-link to="/projects" class="btn btn-primary">
        Get Started
      </router-link>
    </div>

    <div class="features">
      <div class="feature-card">
        <h3>Upload Data</h3>
        <p>Import your omics/metagenomics matrices (TSV/CSV) with flexible row or column orientation.</p>
      </div>
      <div class="feature-card">
        <h3>Configure & Run</h3>
        <p>Choose algorithms (GA, Beam, MCMC), languages (binary, ternary, ratio), and tune parameters.</p>
      </div>
      <div class="feature-card">
        <h3>Explore Results</h3>
        <p>Browse model populations, inspect feature importance, and compare across runs.</p>
      </div>
    </div>

    <div class="status" v-if="health">
      <small>
        API: {{ health.status }} | Engine: {{ health.gpredomicspy_available ? 'ready' : 'mock mode' }}
      </small>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const health = ref(null)

onMounted(async () => {
  try {
    const { data } = await axios.get('/health')
    health.value = data
  } catch (e) {
    console.error('Health check failed:', e)
  }
})
</script>

<style scoped>
.home { text-align: center; }

.hero {
  padding: 3rem 1rem;
}

.hero h1 {
  font-size: 2.5rem;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}

.subtitle {
  font-size: 1.2rem;
  color: var(--text-secondary);
  margin-bottom: 1rem;
}

.description {
  max-width: 600px;
  margin: 0 auto 2rem;
  color: var(--text-muted);
  line-height: 1.6;
}

.btn {
  display: inline-block;
  padding: 0.75rem 2rem;
  border-radius: 6px;
  text-decoration: none;
  font-weight: 600;
  transition: background 0.2s;
}

.btn-primary {
  background: var(--accent);
  color: var(--accent-text);
}

.btn-primary:hover {
  background: var(--accent-hover);
}

.features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
  margin: 3rem 0;
}

.feature-card {
  background: var(--bg-card);
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: var(--shadow);
  text-align: left;
}

.feature-card h3 {
  margin-bottom: 0.5rem;
  color: var(--text-primary);
}

.feature-card p {
  color: var(--text-muted);
  font-size: 0.9rem;
  line-height: 1.5;
}

.status {
  margin-top: 2rem;
  color: var(--text-faint);
}
</style>
