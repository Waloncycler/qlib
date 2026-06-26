<template>
  <div class="app-container" :class="{ 'mobile-sidebar-open': isMobileSidebarOpen }">
    <!-- Mobile Top Bar -->
    <div class="mobile-top-bar glass-panel">
      <div class="mobile-logo-wrapper">
        <span class="logo-text">Data Explorer</span>
      </div>
      <button class="hamburger-btn" @click="isMobileSidebarOpen = !isMobileSidebarOpen">
        <MenuIcon class="icon" />
      </button>
    </div>

    <!-- Mobile Sidebar Backdrop -->
    <div class="sidebar-backdrop" v-if="isMobileSidebarOpen" @click="isMobileSidebarOpen = false"></div>
    <nav class="sidebar glass-panel" :class="{ 'collapsed': !isSidebarOpen }">
      <div class="logo" :class="{ 'centered': !isSidebarOpen }">
        <span class="logo-text" v-if="isSidebarOpen">Data Explorer</span>
        <button class="toggle-btn" @click="isSidebarOpen = !isSidebarOpen" title="Toggle Sidebar">
          <PanelLeftCloseIcon v-if="isSidebarOpen" class="icon toggle-icon" />
          <PanelLeftOpenIcon v-else class="icon toggle-icon" />
        </button>
      </div>
      <div class="nav-links">
        <router-link to="/market" class="nav-item" :title="!isSidebarOpen ? 'Market' : ''" @click="closeMobileSidebar">
          <ActivityIcon class="icon" />
          <span v-if="isSidebarOpen || isMobileView">Market</span>
        </router-link>
        <router-link to="/topics" class="nav-item" :title="!isSidebarOpen ? 'Topics' : ''" @click="closeMobileSidebar">
          <HashIcon class="icon" />
          <span v-if="isSidebarOpen || isMobileView">Topics</span>
        </router-link>
        <router-link to="/stock" class="nav-item" :title="!isSidebarOpen ? 'Stocks' : ''" @click="closeMobileSidebar">
          <TrendingUpIcon class="icon" />
          <span v-if="isSidebarOpen || isMobileView">Stocks</span>
        </router-link>
        <router-link to="/reports" class="nav-item" :title="!isSidebarOpen ? 'AI Reports' : ''" @click="closeMobileSidebar">
          <BookOpenIcon class="icon" />
          <span v-if="isSidebarOpen || isMobileView">AI Reports</span>
        </router-link>
        <router-link to="/wencai" class="nav-item" :title="!isSidebarOpen ? 'AI Wencai' : ''" @click="closeMobileSidebar">
          <BotIcon class="icon" />
          <span v-if="isSidebarOpen || isMobileView">AI Wencai</span>
        </router-link>
        <router-link to="/backtest" class="nav-item" :title="!isSidebarOpen ? 'Backtest' : ''" @click="closeMobileSidebar">
          <LineChartIcon class="icon" />
          <span v-if="isSidebarOpen || isMobileView">Backtest</span>
        </router-link>
      </div>

      <div class="sidebar-footer">
        <button class="global-sync-btn" @click="handleGlobalSync" :disabled="isSyncing" :title="!isSidebarOpen ? 'Global Sync' : ''">
          <RefreshCwIcon class="icon" :class="{ 'spinning': isSyncing }" />
          <span v-if="isSidebarOpen || isMobileView">{{ isSyncing ? 'Syncing Data...' : 'Global Sync' }}</span>
        </button>
      </div>
    </nav>
    <main class="main-content" :class="{ 'expanded': !isSidebarOpen }">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" :key="routeVersion" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ActivityIcon, HashIcon, TrendingUpIcon, PanelLeftCloseIcon, PanelLeftOpenIcon, BotIcon, LineChartIcon, BookOpenIcon, RefreshCwIcon, MenuIcon } from 'lucide-vue-next'
import { useDataLoader } from './composables/useDataLoader'

const isSidebarOpen = ref(true)
const isMobileSidebarOpen = ref(false)
const isMobileView = ref(false)
const isSyncing = ref(false)
const routeVersion = ref(0)
const { triggerBackendRefresh, checkRefreshStatus } = useDataLoader()

const checkMobileView = () => {
  isMobileView.value = window.innerWidth <= 768
  if (!isMobileView.value) {
    isMobileSidebarOpen.value = false
  }
}

const closeMobileSidebar = () => {
  if (isMobileView.value) {
    isMobileSidebarOpen.value = false
  }
}

const handleGlobalSync = async () => {
  if (isSyncing.value) return
  isSyncing.value = true
  
  const res = await triggerBackendRefresh()
  if (res && (res.status === 'started' || res.status === 'busy')) {
    startPolling()
  } else {
    isSyncing.value = false
  }
}

const startPolling = () => {
  const timer = setInterval(async () => {
    const status = await checkRefreshStatus()
    if (!status || !status.running) {
      clearInterval(timer)
      isSyncing.value = false
      if (status && status.last_result === 'success') {
        // Force re-mount current route component to reload fresh data
        routeVersion.value++
      }
    }
  }, 5000)
}

onMounted(async () => {
  // Check if it's already syncing when page loads
  const status = await checkRefreshStatus()
  if (status && status.running) {
    isSyncing.value = true
    startPolling()
  }

  checkMobileView()
  window.addEventListener('resize', checkMobileView)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobileView)
})
</script>

<style scoped>
.app-container {
  display: flex;
  height: 100vh;
  overflow: hidden;
  position: relative;
  flex-direction: row;
}

/* Mobile Top Bar */
.mobile-top-bar {
  display: none;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  width: 100%;
  z-index: 20;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}

.mobile-logo-wrapper {
  display: flex;
  align-items: center;
}

.hamburger-btn {
  background: transparent;
  border: none;
  color: var(--text-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  border-radius: 6px;
}

.sidebar-backdrop {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  z-index: 15;
}

.sidebar {
  width: 240px;
  margin: 16px;
  display: flex;
  flex-direction: column;
  padding: 24px 0;
  z-index: 20;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar.collapsed {
  width: 80px;
  align-items: center;
}

.logo {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  margin-bottom: 40px;
  height: 36px;
}

.logo.centered {
  padding: 0;
  justify-content: center;
  width: 100%;
}

.logo-text {
  font-weight: 700;
  font-size: 1.1rem;
  letter-spacing: -0.02em;
  white-space: nowrap;
}

.toggle-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px;
  border-radius: 6px;
  transition: all 0.2s;
}

.toggle-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
}

.nav-links {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 12px;
  width: 100%;
  box-sizing: border-box;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  text-decoration: none;
  color: var(--text-secondary);
  border-radius: 8px;
  transition: all var(--transition-speed) ease;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
}

.sidebar.collapsed .nav-item {
  padding: 12px;
  justify-content: center;
}

.sidebar.collapsed .nav-links {
  padding: 0 8px;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary);
}

.nav-item.router-link-active {
  background: rgba(59, 130, 246, 0.1);
  color: var(--accent-color);
}

.icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.main-content {
  flex: 1;
  padding: 16px 16px 16px 0;
  overflow-y: auto;
  overflow-x: hidden;
  transition: padding 0.3s;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

.sidebar-footer {
  margin-top: auto;
  padding: 12px;
  width: 100%;
  box-sizing: border-box;
}

.global-sync-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  box-sizing: border-box;
  background: rgba(56, 189, 248, 0.1);
  color: var(--accent-color);
  border: 1px solid rgba(56, 189, 248, 0.2);
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
  font-size: 0.95rem;
  transition: all 0.2s ease;
  white-space: nowrap;
  overflow: hidden;
}

.sidebar.collapsed .global-sync-btn {
  padding: 12px;
  justify-content: center;
}

.global-sync-btn:hover:not(:disabled) {
  background: rgba(56, 189, 248, 0.2);
}

.global-sync-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  100% { transform: rotate(360deg); }
}

/* Responsive Styles */
@media (max-width: 768px) {
  .app-container {
    flex-direction: column;
  }
  
  .mobile-top-bar {
    display: flex;
  }
  
  .sidebar-backdrop {
    display: block;
  }

  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    height: 100vh;
    margin: 0;
    border-radius: 0;
    transform: translateX(-100%);
    width: 260px;
  }

  .app-container.mobile-sidebar-open .sidebar {
    transform: translateX(0);
  }

  .logo .toggle-btn {
    display: none;
  }

  .main-content {
    padding: 16px;
    width: 100%;
    box-sizing: border-box;
  }
}
</style>
