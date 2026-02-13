import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('./views/HomeView.vue'),
  },
  {
    path: '/projects',
    name: 'Projects',
    component: () => import('./views/ProjectsView.vue'),
  },
  {
    path: '/project/:id',
    name: 'Project',
    component: () => import('./views/ProjectView.vue'),
  },
  {
    path: '/project/:id/run',
    name: 'RunAnalysis',
    component: () => import('./views/RunView.vue'),
  },
  {
    path: '/project/:id/results/:jobId',
    name: 'Results',
    component: () => import('./views/ResultsView.vue'),
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
