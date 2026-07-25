import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { NodeDetail, GraphData, EntityResponse, RelationshipResponse, SystemInfo } from '@/types'

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

  // ==================== v2.0 状态操作方法 ====================

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

  // ==================== v3.0 多系统管理 ====================

  /** 当前选中的系统ID */
  const currentSystemId = ref('disease_ontology')

  /** 当前系统信息 */
  const currentSystemInfo = ref<SystemInfo | null>(null)

  /** 所有系统列表 */
  const systemList = ref<SystemInfo[]>([])

  /** ★ v3.0: 当前系统的 prefix（如 MED_） */
  const currentPrefix = computed(() => {
    const sys = systemList.value.find(s => s.system_id === currentSystemId.value)
    return sys?.prefix || 'MED_'
  })

  /** ★ v3.0: 剥离前缀用于展示（MED_Disease → Disease） */
  function displayLabel(fullLabel: string): string {
    const p = currentPrefix.value
    if (p && fullLabel.startsWith(p)) {
      return fullLabel.slice(p.length)
    }
    return fullLabel
  }

  /** 导入向导可见性 */
  const importWizardVisible = ref(false)

  /** 导入来源类型 */
  const importSource = ref<'excel' | 'database'>('excel')

  /** 系统管理对话框可见性 */
  const systemManagerVisible = ref(false)

  function setCurrentSystem(systemId: string) {
    currentSystemId.value = systemId
    const sys = systemList.value.find(s => s.system_id === systemId)
    if (sys) currentSystemInfo.value = sys
  }

  function setSystemList(list: SystemInfo[]) {
    systemList.value = list
  }

  function addSystem(sys: SystemInfo) {
    const idx = systemList.value.findIndex(s => s.system_id === sys.system_id)
    if (idx >= 0) {
      systemList.value[idx] = sys
    } else {
      systemList.value.unshift(sys)
    }
  }

  function removeSystem(systemId: string) {
    systemList.value = systemList.value.filter(s => s.system_id !== systemId)
    // 如果当前系统被删，切回默认
    if (currentSystemId.value === systemId) {
      setCurrentSystem('disease_ontology')
    }
  }

  function openImportWizard(source: 'excel' | 'database') {
    importSource.value = source
    importWizardVisible.value = true
  }

  function closeImportWizard() {
    importWizardVisible.value = false
  }

  function openSystemManager() {
    systemManagerVisible.value = true
  }

  function closeSystemManager() {
    systemManagerVisible.value = false
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
    // v3.0
    currentSystemId,
    currentSystemInfo,
    systemList,
    currentPrefix,
    displayLabel,
    importWizardVisible,
    importSource,
    systemManagerVisible,
    setCurrentSystem,
    setSystemList,
    addSystem,
    removeSystem,
    openImportWizard,
    closeImportWizard,
    openSystemManager,
    closeSystemManager,
  }
})
