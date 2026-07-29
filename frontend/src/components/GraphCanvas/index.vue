<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted, nextTick } from 'vue'
import { ReloadOutlined, PlusOutlined, MinusOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { DataSet, Network } from 'vis-network/standalone'
import { useAppStore } from '@/stores'
import { fetchGraphOverview, fetchNeighborhood, fetchNodeDetail, fetchRelationship } from '@/api'

const store = useAppStore()

const containerRef = ref<HTMLDivElement>()
const loading = ref(false)
const nodeCount = ref(0)
const edgeCount = ref(0)
const expandedNodes = ref<Set<string>>(new Set())
let network: Network | null = null
let currentNodesDS: DataSet<any> | null = null

// v2.0: 缩放控制
const currentScale = ref(1)
const ZOOM_STEP = 0.25
const SCALE_MIN = 0.30   // 最小缩小比例为30%，防止图表缩到过小无法恢复

function safeScale(s: number): boolean {
  return isFinite(s) && s > 0.001
}

function zoomTo(scale: number) {
  if (!network) return
  network.moveTo({ scale, animation: { duration: 250, easingFunction: 'easeInOutQuad' } })
  currentScale.value = scale
}

function handleZoomIn() {
  if (!network) return
  const scale = network.getScale()
  if (!safeScale(scale)) {
    network.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } })
    currentScale.value = network.getScale()
    return
  }
  zoomTo(scale + ZOOM_STEP)
}

function handleZoomOut() {
  if (!network) return
  const scale = network.getScale()
  if (!safeScale(scale)) {
    network.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } })
    currentScale.value = network.getScale()
    return
  }
  zoomTo(Math.max(SCALE_MIN, scale - ZOOM_STEP))
}

/** 节点类型颜色 - 与后端 NODE_COLORS 完全同步 */
const nodeTypeColors: Record<string, string> = {
  Disease: '#f5222d',
  Symptom: '#fa8c16',
  Drug: '#1890ff',
  BodyPart: '#52c41a',
  SideEffect: '#722ed1',
  Department: '#eb2f96',
  Student: '#13c2c2',
  Teacher: '#2f54eb',
  Subject: '#faad14',
  Course: '#a0d911',
  Patient: '#f759ab',
  Hospital: '#722ed1',
  Doctor: '#1677ff',
  Test: '#bfbfbf',
  Exam: '#ff7a45',
  Treatment: '#52c41a',
  Prescription: '#1890ff',
  Diagnosis: '#fa541c',
}

/** 动态备用色板（与后端 _FALLBACK_COLORS 对齐） */
const fallbackColors = [
  '#f5222d', '#fa8c16', '#1890ff', '#52c41a', '#722ed1',
  '#eb2f96', '#13c2c2', '#2f54eb', '#faad14', '#a0d911',
  '#f759ab', '#1677ff', '#ff7a45', '#fa541c', '#9254de',
  '#36cfc9', '#d4380d', '#0958d9', '#389e0d', '#c41d7f',
]

/** 关系类型颜色（按后端原始 type 映射）- 工业配色 */
const edgeTypeColors: Record<string, string> = {
  SUB_CLASS_OF: '#8c8c8c',
  MANIFESTS_IN: '#fa541c',
  TREATS: '#52c41a',
  CONTRAINDICATED_WITH: '#f5222d',
  CAN_SUBSTITUTE: '#1890ff',
  AFFECTS: '#faad14',
  HAS_SIDE_EFFECT: '#fa8c16',
}

function getNodeBg(type: string, fallback?: string): string {
  // 后端分配的颜色优先
  if (fallback && fallback !== '#999999' && fallback !== '#95a5a6') return fallback
  // 前端已知类型映射
  if (nodeTypeColors[type]) return nodeTypeColors[type]
  // 动态分配：基于类型名哈希从备用色板选取
  let hash = 0
  for (let i = 0; i < type.length; i++) {
    hash = ((hash << 5) - hash) + type.charCodeAt(i)
    hash |= 0
  }
  const idx = Math.abs(hash) % fallbackColors.length
  return fallbackColors[idx]
}

function getEdgeClr(rawType?: string): string {
  return edgeTypeColors[rawType || ''] || '#888888'
}

/** 核心渲染函数 */
function renderGraph(nodesData: any[], edgesData: any[]) {
  if (!containerRef.value) return

  nodeCount.value = nodesData.length
  const validNodesData = nodesData.filter((n: any) => n && n.id)
  const nodeIds = new Set(validNodesData.map((n: any) => n.id))
  const validEdgesData = edgesData.filter((e: any) => {
    const sourceId = e?.source || e?.from
    const targetId = e?.target || e?.to
    return e?.id && sourceId && targetId && nodeIds.has(sourceId) && nodeIds.has(targetId)
  })

  nodeCount.value = validNodesData.length
  edgeCount.value = validEdgesData.length
  updateLegend(validNodesData)

  const nodes = new DataSet(
    validNodesData.map((n: any) => { 
      const bg = getNodeBg(n.type, n.color)
      return {
      id: n.id,
      label: n.label || n.name || '',
      color: {
        background: bg,
        border: bg,           // 未选中：边框=背景色，视觉无缝
        highlight: { background: bg, border: '#000000' },  // 选中：黑色边框
        hover: { background: bg, border: '#000000' },
      },
      font: { size: 13, color: '#ffffff', strokeWidth: 1, strokeColor: 'rgba(0,0,0,0.25)' },
      borderWidth: 1.5,
      borderWidthSelected: 8,
      shape: 'box',
      shapeProperties: { borderRadius: 4 },
      size: Math.max(n.size || 16, 12),
      title: `${n.label || n.name} (${n.type || '未知'})`,
      margin: 8,
      _type: n.type,
      }
    }),
  )
  currentNodesDS = nodes

  const edges = new DataSet(
    validEdgesData.map((e: any) => {
      const sourceId = e.source || e.from
      const targetId = e.target || e.to
      return {
        id: e.id,
        from: sourceId,
        to: targetId,
        label: e.label || e.type || '',
        arrows: { to: { enabled: true, scaleFactor: 1 } },
        font: {
          size: 10,
          color: '#8c8c8c',
          align: 'middle',
          background: '#ffffff',
          strokeWidth: 3,
          strokeColor: '#ffffff',
        },
        color: { color: getEdgeClr(e.type), highlight: '#1890ff', hover: '#1890ff' },
        smooth: { enabled: true, type: 'continuous', roundness: 0.3 },
        width: 1.5,
        hoverWidth: 2.5,
        selectionWidth: 2,
        _rawType: e.type,
      }
    }),
  )

  const options = {
    physics: {
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {
        gravitationalConstant: -40,
        centralGravity: 0.008,
        springLength: 160,
        springConstant: 0.06,
        damping: 0.4,
      },
      maxVelocity: 30,
      stabilization: { iterations: 150, fit: true },
    },
    interaction: {
      hover: true,
      tooltipDelay: 150,
      zoomView: true,
      dragView: false,
      keyboard: true,
    },
  }

  if (network) {
    network.setData({ nodes, edges })
    updateBBox()
    // 若当前比例过低（eg 数据刷新前被缩到极小），重置为 fit 视图
    const s = network.getScale()
    if (!safeScale(s)) {
      network.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } })
      currentScale.value = network.getScale()
    }
    network.stabilize(60)
  } else {
    network = new Network(containerRef.value, { nodes, edges }, options)

    // ---- 缩放事件：同步当前比例 + 下限保护 ----
    network.on('zoom', () => {
      const s = network!.getScale()
      if (s < SCALE_MIN) {
        // 防止缩放到过小导致不可见，回弹到最低可见比例
        network!.moveTo({ scale: SCALE_MIN })
        currentScale.value = SCALE_MIN
        return
      }
      currentScale.value = s
    })
    // 初始化缩放值
    currentScale.value = network.getScale()

    // ---- 单击节点/边：选中 → 触发详情展示 ----
    network.on('click', async (params: any) => {
      // 优先处理节点点击
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0]
        const node = currentNodesDS?.get(nodeId) as any
        if (node) {
          store.selectNode(node._type || '', node.label || '', nodeId)
        }
        return
      }
      // 其次处理边点击：获取关系详情（源实体→关系→目标实体）并展示
      if (params.edges.length > 0) {
        const edgeId = params.edges[0]
        try {
          const rel = await fetchRelationship(edgeId)
          store.selectRelationship(rel)
        } catch (e: any) {
          console.error('加载关系详情失败:', e)
          message.error(e?.response?.data?.detail || '加载关系详情失败，请重试')
        }
        return
      }
      // 点击空白取消选中
      store.clearSelection()
    })

    // ---- 启动自定义带边界约束的平移 ----
    setupCustomPan()
    updateBBox()
  }
}

// ===== 节点包围盒缓存（辅助边界计算） =====
let nodesMinX = 0, nodesMaxX = 0, nodesMinY = 0, nodesMaxY = 0
let bboxValid = false

function updateBBox() {
  if (!network) return
  const positions = network.getPositions()
  const ids = Object.keys(positions)
  if (ids.length === 0) { bboxValid = false; return }
  nodesMinX = Infinity; nodesMaxX = -Infinity
  nodesMinY = Infinity; nodesMaxY = -Infinity
  for (const id of ids) {
    const p = positions[id]
    if (p.x < nodesMinX) nodesMinX = p.x
    if (p.x > nodesMaxX) nodesMaxX = p.x
    if (p.y < nodesMinY) nodesMinY = p.y
    if (p.y > nodesMaxY) nodesMaxY = p.y
  }
  bboxValid = true
}

function clampViewPos(x: number, y: number, scale: number, container: HTMLElement): { x: number; y: number } {
  if (!bboxValid) return { x, y }
  const vw = container.clientWidth / scale
  const vh = container.clientHeight / scale
  const viewLeft = x - vw / 2
  const viewRight = x + vw / 2
  const viewTop = y - vh / 2
  const viewBottom = y + vh / 2

  let nx = x, ny = y
  if (viewLeft > nodesMaxX) nx = nodesMaxX - vw / 2 + vw * 0.2
  else if (viewRight < nodesMinX) nx = nodesMinX + vw / 2 - vw * 0.2
  if (viewTop > nodesMaxY) ny = nodesMaxY - vh / 2 + vh * 0.2
  else if (viewBottom < nodesMinY) ny = nodesMinY + vh / 2 - vh * 0.2
  return { x: nx, y: ny }
}

// ===== 自定义平移：通过原生 DOM 事件实现，在拖拽过程中实时钳制位置 =====
let panning = false
let panStartClientX = 0, panStartClientY = 0
let panStartViewX = 0, panStartViewY = 0

function onMouseDown(e: MouseEvent) {
  if (!network || !containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  const canvasPos = network.DOMtoCanvas({ x: e.clientX - rect.left, y: e.clientY - rect.top })
  const nodeId = network.getNodeAt(canvasPos)
  if (nodeId) return  // 点击在节点上，交给 vis-network 处理

  panning = true
  panStartClientX = e.clientX
  panStartClientY = e.clientY
  const vp = network.getViewPosition()
  panStartViewX = vp.x
  panStartViewY = vp.y
  e.preventDefault()
}

function onMouseMove(e: MouseEvent) {
  if (!panning || !network || !containerRef.value) return
  const scale = network.getScale()
  const dx = -(e.clientX - panStartClientX) / scale
  const dy = -(e.clientY - panStartClientY) / scale
  const clamped = clampViewPos(panStartViewX + dx, panStartViewY + dy, scale, containerRef.value)
  network.moveTo({ position: { x: clamped.x, y: clamped.y }, scale, animation: false })
}

function onMouseUp() {
  panning = false
}

function setupCustomPan() {
  if (!containerRef.value) return
  containerRef.value.addEventListener('mousedown', onMouseDown)
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}

function teardownCustomPan() {
  panning = false
  if (containerRef.value) {
    containerRef.value.removeEventListener('mousedown', onMouseDown)
  }
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
}

/** 动态图例：从当前节点数据中提取去重类型 */
const legendItems = ref<{ type: string; color: string }[]>([])

function updateLegend(nodesData: any[]) {
  const seen = new Map<string, string>()
  for (const n of nodesData) {
    const t = n.type || 'Unknown'
    if (!seen.has(t)) {
      seen.set(t, getNodeBg(t, n.color))
    }
  }
  legendItems.value = Array.from(seen.entries()).map(([type, color]) => ({ type, color }))
}

// ===== 图谱全局数据（可渐进扩展） =====
let mergedNodes: any[] = []
let mergedEdges: any[] = []

/** 系统切换代数计数器，用于取消过期的异步邻域请求 */
let loadGeneration = 0

async function loadData() {
  loading.value = true
  try {
    const data = await fetchGraphOverview(store.currentSystemId)
    mergedNodes = [...(data.nodes || [])]
    mergedEdges = [...(data.edges || [])]
    store.setGraphData(data)
    await nextTick()
    renderGraph(mergedNodes, mergedEdges)
  } catch (e) {
    console.error('加载图谱数据失败:', e)
  } finally {
    loading.value = false
  }
}

function handleRefresh() {
  mergedNodes = []
  mergedEdges = []
  expandedNodes.value = new Set()
  loadData()
}

// ===== 选中节点心跳动画 =====
let heartbeatTimer: ReturnType<typeof setInterval> | null = null
let heartbeatNodeId: string | null = null
let heartbeatPhase = false

function startHeartbeat(nodeId: string) {
  stopHeartbeat()
  heartbeatNodeId = nodeId
  heartbeatPhase = false
  // 每 500ms 节点大小+阴影脉冲交替，模拟心脏跳动
  heartbeatTimer = setInterval(() => {
    if (!network || !heartbeatNodeId) return
    heartbeatPhase = !heartbeatPhase
    const nodesDS = (network as any).body?.data?.nodes
    if (!nodesDS) return
    nodesDS.update({
      id: heartbeatNodeId,
      margin: heartbeatPhase ? 16 : 6,
      font: { size: heartbeatPhase ? 16 : 13, color: '#ffffff', strokeWidth: 1, strokeColor: 'rgba(0,0,0,0.25)' },
      shadow: {
        enabled: true,
        color: heartbeatPhase ? 'rgba(250, 84, 28, 0.9)' : 'rgba(250, 84, 28, 0.1)',
        size: heartbeatPhase ? 45 : 12,
        x: 0,
        y: 0,
      },
    })
  }, 500)
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }
  // 恢复节点原始样式
  if (network && heartbeatNodeId) {
    const nodesDS = (network as any).body?.data?.nodes
    if (nodesDS) {
      nodesDS.update({
        id: heartbeatNodeId,
        margin: 8,
        font: { size: 13, color: '#ffffff', strokeWidth: 1, strokeColor: 'rgba(0,0,0,0.25)' },
        shadow: { enabled: false },
      })
    }
  }
  heartbeatNodeId = null
}

// ===== 监听选中节点：展开邻域 + 聚焦 + 设置详情 =====
let pendingElementId: string | null = null

watch(
  () => store.selectedNode,
  async (node) => {
    if (!network || !node || !node.elementId) {
      stopHeartbeat()
      return
    }

    // 防止重复触发
    if (pendingElementId === node.elementId) return
    pendingElementId = node.elementId

    try {
      // 并行请求详情和邻域
      const myGen = loadGeneration
      const [detail, neighborData] = await Promise.all([
        fetchNodeDetail(node.elementId, store.currentSystemId),
        fetchNeighborhood(node.elementId, 1, store.currentSystemId).catch(() => null),
      ])

      // 系统切换后取消过期的邻域合并，防止跨系统节点泄露
      if (myGen !== loadGeneration) return

      // 更新详情到 store
      store.selectedNodeDetail = detail

      // 合并邻域数据到图谱
      if (neighborData) {
        const existingNodeIds = new Set(mergedNodes.map((n: any) => n.id))
        const existingEdgeIds = new Set(mergedEdges.map((e: any) => e.id))

        const newNodes = (neighborData.nodes || []).filter((n: any) => !existingNodeIds.has(n.id))
        const newEdges = (neighborData.edges || []).filter((e: any) => !existingEdgeIds.has(e.id))

        if (newNodes.length > 0 || newEdges.length > 0) {
          mergedNodes.push(...newNodes)
          mergedEdges.push(...newEdges)
          renderGraph(mergedNodes, mergedEdges)
        }
      }

      // 高亮并聚焦到目标节点
      await nextTick()
      network.selectNodes([node.elementId])
      startHeartbeat(node.elementId)
      network.focus(node.elementId, {
        scale: 1.5,
        animation: { duration: 500, easingFunction: 'easeInOutQuad' },
      })
      expandedNodes.value.add(node.elementId)
    } catch (e) {
      console.error('展开节点失败:', e)
      // 至少尝试聚焦
      try {
        network.selectNodes([node.elementId])
        network.focus(node.elementId, { scale: 1.2, animation: true })
      } catch {}
    } finally {
      pendingElementId = null
    }
  },
)

// ===== v3.0: 系统切换时重新加载图谱 =====
watch(
  () => store.currentSystemId,
  () => {
    // 递增代数，使进行中的邻域请求失效
    loadGeneration++
    mergedNodes = []
    mergedEdges = []
    expandedNodes.value = new Set()
    // 清除选中状态，防止旧系统节点残留
    store.clearSelection()
    loadData()
  },
)

onMounted(loadData)

onUnmounted(() => {
  stopHeartbeat()
  teardownCustomPan()
  if (network) {
    network.destroy()
    network = null
  }
})
</script>

<template>
  <div class="graph-canvas">
    <div class="graph-header">
      <div class="header-left">
        <span class="header-title">图谱</span>
        <a-tag v-if="loading" color="processing">加载中...</a-tag>
        <a-tag color="default">节点 {{ nodeCount }}</a-tag>
        <a-tag color="default">边 {{ edgeCount }}</a-tag>
        <span class="graph-hint">点击节点展开关系 | 滚轮缩放 | 拖拽平移</span>
      </div>
      <div class="header-actions">
        <a-button size="small" @click="handleRefresh" :loading="loading">
          <template #icon><ReloadOutlined /></template>
          重置
        </a-button>
      </div>
    </div>

    <!-- 图例（动态生成） -->
    <div class="graph-legend">
      <span v-for="item in legendItems" :key="item.type" class="legend-item">
        <i class="legend-dot" :style="{ background: item.color }"></i>
        {{ item.type }}
      </span>
    </div>

    <div class="graph-body">
      <div ref="containerRef" class="graph-container" />
      <a-empty
        v-if="!loading && nodeCount === 0"
        description="暂无图谱数据"
        style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%)"
      />
      <!-- v2.0: 缩放控制 -->
      <div class="zoom-controls">
        <a-button size="small" shape="circle" @click="handleZoomIn" :disabled="!network">
          <template #icon><PlusOutlined /></template>
        </a-button>
        <span class="zoom-label">{{ Math.round(currentScale * 100) }}%</span>
        <a-button size="small" shape="circle" @click="handleZoomOut" :disabled="!network">
          <template #icon><MinusOutlined /></template>
        </a-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.graph-canvas {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f5f7fa;
}

.graph-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
  background: #fff;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.header-title {
  font-size: 13px;
  font-weight: 600;
  color: #262626;
}

.graph-hint {
  font-size: 11px;
  color: #bfbfbf;
  margin-left: 6px;
}

/* 图例 */
.graph-legend {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 6px 14px;
  border-bottom: 1px solid #f0f0f0;
  background: #fff;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: #595959;
}

.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.08);
}

.graph-body {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: #f5f7fa;
}

.graph-container {
  width: 100%;
  height: 100%;
}

/* v2.0: 缩放控制 */
.zoom-controls {
  position: absolute;
  bottom: 16px;
  right: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  background: #fff;
  border-radius: 20px;
  padding: 6px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.zoom-controls :deep(.ant-btn) {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.zoom-label {
  font-size: 11px;
  color: #8c8c8c;
  line-height: 1;
  padding: 2px 0;
  user-select: none;
}
</style>
