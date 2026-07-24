import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { NodeDetail, GraphData, EntityResponse, RelationshipResponse } from '@/types'

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

  // v2.0 编辑状态
  const entityEditorVisible = ref(false)
  const entityEditorMode = ref<'create' | 'edit'>('create')
  const editingEntity = ref<EntityResponse | null>(null)
  const editingElementId = ref('')
  const presetLabel = ref('')

  const relationshipEditorVisible = ref(false)
  const relationshipEditorMode = ref<'create' | 'edit'>('create')
  const editingRelationship = ref<RelationshipResponse | null>(null)
  const editingRelationshipSourceId = ref('')
  const editingRelationshipSourceName = ref('')
  const presetRelationshipType = ref('')

  // v2.0: 关系详情（选中关系时的展示）
  const selectedRelationship = ref<RelationshipResponse | null>(null)

  // 本体树刷新计数器
  const treeRefreshKey = ref(0)

  function selectNode(type: string, name: string, elementId = '') {
    selectedNode.value = { type, name, elementId }
  }

  function clearSelection() {
    selectedNode.value = null
    selectedNodeDetail.value = null
    selectedRelationship.value = null
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

  // ---- 编辑弹窗控制 ----

  function openEntityEditor(mode: 'create' | 'edit', entity?: EntityResponse) {
    entityEditorMode.value = mode
    editingEntity.value = entity || null
    editingElementId.value = entity?.element_id || ''
    presetLabel.value = ''
    entityEditorVisible.value = true
  }

  function openCreateEntityWithLabel(label: string) {
    entityEditorMode.value = 'create'
    editingEntity.value = null
    editingElementId.value = ''
    presetLabel.value = label
    entityEditorVisible.value = true
  }

  function closeEntityEditor() {
    entityEditorVisible.value = false
  }

  function openRelationshipEditor(sourceId: string, sourceName: string) {
    relationshipEditorMode.value = 'create'
    editingRelationship.value = null
    editingRelationshipSourceId.value = sourceId
    editingRelationshipSourceName.value = sourceName
    relationshipEditorVisible.value = true
  }

  function openEditRelationshipEditor(rel: RelationshipResponse) {
    relationshipEditorMode.value = 'edit'
    editingRelationship.value = rel
    editingRelationshipSourceId.value = rel.source_id
    editingRelationshipSourceName.value = rel.source_name
    relationshipEditorVisible.value = true
  }

  function openCreateRelationshipWithType(type: string) {
    relationshipEditorMode.value = 'create'
    editingRelationship.value = null
    editingRelationshipSourceId.value = ''
    editingRelationshipSourceName.value = ''
    presetRelationshipType.value = type
    relationshipEditorVisible.value = true
  }

  function closeRelationshipEditor() {
    relationshipEditorVisible.value = false
    presetRelationshipType.value = ''
  }

  function triggerTreeRefresh() {
    treeRefreshKey.value++
  }

  return {
    selectedNode,
    selectedNodeDetail,
    nodeDetailLoading,
    graphData,
    graphLoading,
    leftCollapsed,
    rightCollapsed,
    entityEditorVisible,
    entityEditorMode,
    editingEntity,
    editingElementId,
    presetLabel,
    relationshipEditorVisible,
    relationshipEditorMode,
    editingRelationship,
    editingRelationshipSourceId,
    editingRelationshipSourceName,
    presetRelationshipType,
    selectedRelationship,
    treeRefreshKey,
    selectNode,
    clearSelection,
    setGraphData,
    toggleLeft,
    toggleRight,
    openEntityEditor,
    openCreateEntityWithLabel,
    closeEntityEditor,
    openRelationshipEditor,
    openEditRelationshipEditor,
    openCreateRelationshipWithType,
    closeRelationshipEditor,
    triggerTreeRefresh,
  }
})
