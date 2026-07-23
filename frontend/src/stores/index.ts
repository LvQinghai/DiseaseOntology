import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { NodeDetail, GraphData } from '@/types'

export const useAppStore = defineStore('app', () => {
  // 当前选中的节点
  const selectedNode = ref<{ type: string; name: string; elementId: string } | null>(null)
  const selectedNodeDetail = ref<NodeDetail | null>(null)
  const nodeDetailLoading = ref(false)

  // 图谱数据
  const graphData = ref<GraphData | null>(null)
  const graphLoading = ref(false)

  // 左侧面板折叠
  const leftCollapsed = ref(false)
  const rightCollapsed = ref(false)

  function selectNode(type: string, name: string, elementId = '') {
    selectedNode.value = { type, name, elementId }
  }

  function clearSelection() {
    selectedNode.value = null
    selectedNodeDetail.value = null
  }

  function setGraphData(data: GraphData) {
    graphData.value = data
  }

  function toggleLeft() {
    leftCollapsed.value = !leftCollapsed.value
  }

  function toggleRight() {
    rightCollapsed.value = !rightCollapsed.value
  }

  return {
    selectedNode,
    selectedNodeDetail,
    nodeDetailLoading,
    graphData,
    graphLoading,
    leftCollapsed,
    rightCollapsed,
    selectNode,
    clearSelection,
    setGraphData,
    toggleLeft,
    toggleRight,
  }
})
