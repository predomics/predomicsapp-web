<template>
  <div id="app">
    <nav class="navbar">
      <router-link to="/" class="brand">PredomicsApp</router-link>
      <div class="nav-links">
        <router-link to="/projects">Projects</router-link>
      </div>
    </nav>
    <main class="container">
      <router-view />
    </main>
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f5f7fa;
  color: #2c3e50;
}

.navbar {
  display: flex;
  align-items: center;
  padding: 0.75rem 2rem;
  background: #1a1a2e;
  color: white;
}

.navbar .brand {
  font-size: 1.25rem;
  font-weight: 700;
  color: #4fc3f7;
  text-decoration: none;
}

.nav-links {
  margin-left: 2rem;
  display: flex;
  gap: 1.5rem;
}

.nav-links a {
  color: #b0bec5;
  text-decoration: none;
  font-size: 0.9rem;
}

.nav-links a.router-link-active {
  color: white;
}

.container {
  max-width: 1200px;
  margin: 2rem auto;
  padding: 0 1rem;
}
</style>
