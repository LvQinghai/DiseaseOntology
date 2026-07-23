<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted, nextTick } from 'vue'
import { ReloadOutlined, AimOutlined } from '@ant-design/icons-vue'
import { DataSet, Network } from 'vis-network/standalone'
import { useAppStore } from '@/stores'
import { fetchGraphOverview, fetchNeighborhood, fetchNodeDetail } from '@/api'

const store = useAppStore()

const containerRef = ref<HTMLDivElement>()
const loading = ref(false)
const nodeCount = ref(0)
const edgeCount = ref(0)
const expandedNodes = ref<Set<string>>(new Set())
let network: Network | null = null

/** 节点类型颜色 - 工业专业配色 */
const nodeTypeColors: Record<string, string> = {
  Disease: '#f5222d',
  Symptom: '#fa8c16',
  Drug: '#1890ff',
  BodyPart: '#52c41a',
  SideEffect: '#722ed1',
}

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
  return fallback || nodeTypeColors[type] || '#95a5a6'
}

function getEdgeClr(rawType?: string): string {
  return edgeTypeColors[rawType || ''] || '#888888'
}

/** 核心渲染函数 */
function renderGraph(nodesData: any[], edgesData: any[]) {
  if (!containerRef.value) return

  nodeCount.value = nodesData.length
  edgeCount.value = edgesData.length

  const nodes = new DataSet(
    nodesData.map((n: any) => ({
      id: n.id,
      label: n.label || n.name || '',
      color: {
        background: getNodeBg(n.type, n.color),
        border: '#ffffff',
        highlight: { background: getNodeBg(n.type, n.color), border: '#333333' },
        hover: { background: getNodeBg(n.type, n.color), border: '#555555' },
      },
      font: { size: 13, color: '#ffffff', strokeWidth: 1, strokeColor: 'rgba(0,0,0,0.25)' },
      borderWidth: 1.5,
      shape: 'box',
      shapeProperties: { borderRadius: 4 },
      size: Math.max(n.size || 16, 12),
      title: `<div style="padding:4px 8px;font-size:13px"><b>${n.label || n.name}</b><br/><span style="font-size:11px;opacity:0.8">${n.type || ''}</span></div>`,
      margin: 8,
      _type: n.type,
    })),
  )

  const edges = new DataSet(
    edgesData.map((e: any) => {
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
      dragView: true,
      keyboard: true,
    },
  }

  if (network) {
    network.setData({ nodes, edges })
    network.stabilize(60)
  } else {
    network = new Network(containerRef.value, { nodes, edges }, options)

    // ---- 单击节点：选中 → 触发 watch ----
    network.on('click', (params: any) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0]
        const node = nodes.get(nodeId) as any
        if (node) {
          store.selectNode(node._type || '', node.label || '', nodeId)
        }
      } else {
        // 点击空白取消选中
        store.clearSelection()
      }
    })
  }
}

// ===== 图谱全局数据（可渐进扩展） =====
let mergedNodes: any[] = []
let mergedEdges: any[] = []

async function loadData() {
  loading.value = true
  try {
    const data = await fetchGraphOverview()
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

// ===== 监听选中节点：展开邻域 + 聚焦 + 设置详情 =====
let pendingElementId: string | null = null

watch(
  () => store.selectedNode,
  async (node) => {
    if (!network || !node || !node.elementId) return

    // 防止重复触发
    if (pendingElementId === node.elementId) return
    pendingElementId = node.elementId

    try {
      // 并行请求详情和邻域
      const [detail, neighborData] = await Promise.all([
        fetchNodeDetail(node.elementId),
        fetchNeighborhood(node.elementId, 1).catch(() => null),
      ])

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

onMounted(loadData)

onUnmounted(() => {
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

    <!-- 图例 -->
    <div class="graph-legend">
      <span v-for="(color, type) in nodeTypeColors" :key="type" class="legend-item">
        <i class="legend-dot" :style="{ background: color }"></i>
        {{ type }}
      </span>
    </div>

    <div class="graph-body">
      <div ref="containerRef" class="graph-container" />
      <a-empty
        v-if="!loading && nodeCount === 0"
        description="暂无图谱数据"
        style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%)"
      />
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
</style>
