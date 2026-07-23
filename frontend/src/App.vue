<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons-vue'
import OntologyBrowser from './components/OntologyBrowser/index.vue'
import GraphCanvas from './components/GraphCanvas/index.vue'
import QueryPanel from './components/QueryPanel/index.vue'
import { useAppStore } from './stores'

const store = useAppStore()

// ===== 面板拖拽调整宽度 =====
const leftWidth = ref(260)
const centerWidth = ref(380)
const MIN_WIDTH = 200
const MAX_LEFT = 500
const MAX_CENTER = 700

interface DragState {
  target: 'left' | 'center'
  startX: number
  startWidth: number
}

const dragging = ref<DragState | null>(null)

function startResize(target: 'left' | 'center', e: MouseEvent) {
  e.preventDefault()
  // 拖拽时自动展开已折叠面板
  if (target === 'left' && store.leftCollapsed) {
    store.toggleLeft()
  }
  const currentWidth = target === 'left' ? leftWidth.value : centerWidth.value
  dragging.value = { target, startX: e.clientX, startWidth: currentWidth }
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function onMouseMove(e: MouseEvent) {
  if (!dragging.value) return
  const { target, startX, startWidth } = dragging.value
  const delta = e.clientX - startX
  const maxW = target === 'left' ? MAX_LEFT : MAX_CENTER
  const newWidth = Math.min(maxW, Math.max(MIN_WIDTH, startWidth + delta))
  if (target === 'left') {
    leftWidth.value = newWidth
  } else {
    centerWidth.value = newWidth
  }
}

function onMouseUp() {
  if (!dragging.value) return
  dragging.value = null
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

onMounted(() => {
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
})

onUnmounted(() => {
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
})

// 面板动态样式
const leftPanelStyle = computed(() => ({
  width: store.leftCollapsed ? '0px' : leftWidth.value + 'px',
  minWidth: store.leftCollapsed ? '0px' : leftWidth.value + 'px',
}))

const centerPanelStyle = computed(() => ({
  width: centerWidth.value + 'px',
  minWidth: centerWidth.value + 'px',
}))

const rightPanelStyle = computed(() => {
  if (store.rightCollapsed) {
    return { flex: '0 0 0px', width: '0px', minWidth: '0px', borderLeft: 'none', overflow: 'hidden' }
  }
  return { flex: '1 1 0%' }
})
</script>

<template>
  <div class="app-layout">
    <!-- 顶部栏 -->
    <header class="app-header">
      <div class="header-left">
        <span class="app-logo">●</span>
        <span class="app-title">疾病本体知识图谱平台 v1.0</span>
      </div>
      <div class="header-right">
        <span class="header-subtitle">基于知识图谱的可视化系统</span>
      </div>
    </header>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧：本体与关系浏览器 -->
      <aside class="panel-left" :style="leftPanelStyle">
        <OntologyBrowser v-if="!store.leftCollapsed" />
      </aside>

      <!-- 左分隔条（拖拽调整 + 折叠按钮） -->
      <div class="panel-divider" @mousedown="startResize('left', $event)">
        <span class="divider-collapse-btn" @mousedown.stop @click="store.toggleLeft">
          <MenuFoldOutlined v-if="!store.leftCollapsed" />
          <MenuUnfoldOutlined v-else />
        </span>
      </div>

      <!-- 中间：详情 + 智能问答 -->
      <main class="panel-center" :style="centerPanelStyle">
        <QueryPanel />
      </main>

      <!-- 右分隔条（拖拽调整 + 折叠按钮） -->
      <div class="panel-divider" @mousedown="startResize('center', $event)">
        <span class="divider-collapse-btn" @mousedown.stop @click="store.toggleRight">
          <MenuFoldOutlined v-if="!store.rightCollapsed" />
          <MenuUnfoldOutlined v-else />
        </span>
      </div>

      <!-- 右侧：图谱画布 -->
      <aside class="panel-right" :style="rightPanelStyle">
        <GraphCanvas v-if="!store.rightCollapsed" />
      </aside>
    </div>
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: #f0f2f5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.app-layout {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 顶部栏 - 工业深蓝底色 */
.app-header {
  height: 48px;
  background: linear-gradient(135deg, #001529 0%, #002140 50%, #001f33 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
  z-index: 100;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.06);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.app-logo {
  color: #1890ff;
  font-size: 16px;
  filter: drop-shadow(0 0 6px rgba(24, 144, 255, 0.4));
}

.app-title {
  color: rgba(255, 255, 255, 0.95);
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.3px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.header-subtitle {
  color: rgba(255, 255, 255, 0.45);
  font-size: 12px;
}

/* 主内容区 */
.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

/* 左侧面板 */
.panel-left {
  background: #fff;
  border-right: 1px solid #e8e8e8;
  overflow: hidden;
  transition: width 0.15s, min-width 0.15s;
  box-shadow: 2px 0 6px rgba(0, 0, 0, 0.04);
}

/* 中间面板（详情 + 智能问答） */
.panel-center {
  background: #fafafa;
  overflow: hidden;
  transition: width 0.15s, min-width 0.15s;
}

/* 右侧面板（图谱画布） */
.panel-right {
  background: #fafafa;
  overflow: hidden;
  border-left: 1px solid #e8e8e8;
  box-shadow: -2px 0 6px rgba(0, 0, 0, 0.04);
}

/* 可拖拽分隔条 */
.panel-divider {
  width: 4px;
  min-width: 4px;
  background: transparent;
  cursor: col-resize;
  flex-shrink: 0;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.25s;
  z-index: 5;
}

.panel-divider:hover {
  background: #1890ff;
}

/* 分隔条上的折叠按钮 */
.divider-collapse-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 22px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 10px;
  color: #595959;
  background: #fafafa;
  border: 1px solid #e8e8e8;
  border-radius: 3px;
  z-index: 6;
  user-select: none;
  transition: all 0.25s;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.divider-collapse-btn:hover {
  background: #1890ff;
  color: #fff;
  border-color: #1890ff;
  box-shadow: 0 2px 6px rgba(24, 144, 255, 0.3);
}
</style>
