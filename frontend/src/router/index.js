import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/market'
  },
  {
    path: '/market',
    name: 'Market',
    component: () => import('../views/MarketDashboard.vue')
  },
  {
    path: '/topics',
    name: 'Topics',
    component: () => import('../views/TopicDashboard.vue')
  },
  {
    path: '/reports',
    name: 'Reports',
    component: () => import('../views/AiReportDashboard.vue')
  },
  {
    path: '/stock/:symbol?',
    name: 'Stock',
    component: () => import('../views/StockDashboard.vue'),
    props: true
  },
  {
    path: '/wencai',
    redirect: '/market'
  },
  {
    path: '/backtest',
    name: 'Backtest',
    component: () => import('../views/Backtest.vue')
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

export default router
