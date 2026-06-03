<template>
  <div class="app-container">
    <nav class="sidebar glass-panel" :class="{ 'collapsed': !isSidebarOpen }">
      <div class="logo" :class="{ 'centered': !isSidebarOpen }">
        <span class="logo-text" v-if="isSidebarOpen">Data Explorer</span>
        <button class="toggle-btn" @click="isSidebarOpen = !isSidebarOpen" title="Toggle Sidebar">
          <PanelLeftCloseIcon v-if="isSidebarOpen" class="icon toggle-icon" />
          <PanelLeftOpenIcon v-else class="icon toggle-icon" />
        </button>
      </div>
      <div class="nav-links">
        <router-link to="/market" class="nav-item" :title="!isSidebarOpen ? 'Market' : ''">
          <ActivityIcon class="icon" />
          <span v-if="isSidebarOpen">Market</span>
        </router-link>
        <router-link to="/topics" class="nav-item" :title="!isSidebarOpen ? 'Topics' : ''">
          <HashIcon class="icon" />
          <span v-if="isSidebarOpen">Topics</span>
        </router-link>
        <router-link to="/stock" class="nav-item" :title="!isSidebarOpen ? 'Stocks' : ''">
          <TrendingUpIcon class="icon" />
          <span v-if="isSidebarOpen">Stocks</span>
        </router-link>
        <router-link to="/reports" class="nav-item" :title="!isSidebarOpen ? 'AI Reports' : ''">
          <BookOpenIcon class="icon" />
          <span v-if="isSidebarOpen">AI Reports</span>
        </router-link>
        <router-link to="/wencai" class="nav-item" :title="!isSidebarOpen ? 'AI Wencai' : ''">
          <BotIcon class="icon" />
          <span v-if="isSidebarOpen">AI Wencai</span>
        </router-link>
        <router-link to="/backtest" class="nav-item" :title="!isSidebarOpen ? 'Backtest' : ''">
          <LineChartIcon class="icon" />
          <span v-if="isSidebarOpen">Backtest</span>
        </router-link>
      </div>
    </nav>
    <main class="main-content" :class="{ 'expanded': !isSidebarOpen }">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ActivityIcon, HashIcon, TrendingUpIcon, PanelLeftCloseIcon, PanelLeftOpenIcon, BotIcon, LineChartIcon, BookOpenIcon } from 'lucide-vue-next'

const isSidebarOpen = ref(true)
</script>

<style scoped>
.app-container {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  width: 240px;
  margin: 16px;
  display: flex;
  flex-direction: column;
  padding: 24px 0;
  z-index: 10;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
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
</style>
