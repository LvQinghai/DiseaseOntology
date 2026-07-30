import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  NodeDetail, GraphData, EntityResponse, RelationshipResponse, SystemInfo,
  ValidationReport, ExecuteResult,
  RelationSemanticInfo, SystemSemanticsResponse,
} from '@/types'
import { fetchRelationSemantics } from '@/api'

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

  // 图谱点击后的左侧树联动选中项（关系点击时保留关系详情，同时同步树选中）
  const selectedTreeNode = ref<{ type: string; name: string; elementId: string } | null>(null)

  // 本体树刷新计数器
  const treeRefreshKey = ref(0)

  // ==================== v2.0 状态操作方法 ====================

  function selectNode(type: string, name: string, elementId = '') {
    const node = { type, name, elementId }
    selectedNode.value = node
    selectedTreeNode.value = node
    // 选中实体时清空关系选中，避免详情面板冲突
    selectedRelationship.value = null
  }

  function selectRelationship(rel: RelationshipResponse) {
    selectedRelationship.value = rel
    // 关系详情仍由中间面板展示；selectedTreeNode 用于左侧树联动选中
    selectedTreeNode.value = {
      type: '__RELATIONSHIP__',
      name: rel.type,
      elementId: '',
    }
    selectedNode.value = null
    selectedNodeDetail.value = null
  }

  function clearSelection() {
    selectedNode.value = null
    selectedNodeDetail.value = null
    selectedRelationship.value = null
    // 同时关闭关系编辑器，防止旧系统数据残留
    relationshipEditorVisible.value = false
    presetRelationshipType.value = ''
    editingRelationship.value = null
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
    editingRelationship.value = null
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

  // ==================== v3.5 导入向导状态 ====================

  /** 导入模式: 'new' 创建全新图谱 / 'append' 追加到已有图谱 */
  const importMode = ref<'new' | 'append'>('new')

  /** 追加模式的目标系统ID */
  const appendTargetSystemId = ref('')

  /** 新建模式下的自定义前缀 */
  const newSystemPrefix = ref('')

  /** 新建模式下的系统名称（临时表单） */
  const newSystemName = ref('')

  /** 新建模式下的系统描述（临时表单） */
  const newSystemDesc = ref('')

  /** 当前导入步骤 (0-4) */
  const importStep = ref(0)

  /** ★ v3.5: 验证报告 */
  const validationReport = ref<ValidationReport | null>(null)

  /** ★ v3.5: 导入执行结果 */
  const executeResult = ref<ExecuteResult | null>(null)

  /** ★ v3.5: 追加模式冲突处理策略: 'skip' | 'merge' | 'overwrite' */
  const conflictStrategy = ref<'skip' | 'merge' | 'overwrite'>('merge')

  /** ★ v3.5: 上次操作的快照ID（供回滚使用） */
  const lastSnapshotId = ref<string | null>(null)

  // ==================== 编辑器中的节点标签 ====================

  /** 编辑器可用标签（用于下拉选择） */
  const editorLabels = ref<string[]>([])

  /** 系统管理对话框可见性 */
  const systemManagerVisible = ref(false)

  // ==================== v3.6 关系语义 ====================

  /** 当前系统的关系语义配置 */
  const relationSemantics = ref<RelationSemanticInfo[]>([])

  /** 关系语义编辑抽屉可见性 */
  const semanticsDrawerVisible = ref(false)

  /** 关系语义加载中 */
  const semanticsLoading = ref(false)

  async function loadRelationSemantics(prefix: string) {
    semanticsLoading.value = true
    try {
      const resp: SystemSemanticsResponse = await fetchRelationSemantics(prefix)
      relationSemantics.value = resp.semantics
    } catch {
      relationSemantics.value = []
    } finally {
      semanticsLoading.value = false
    }
  }

  function openSemanticsDrawer() {
    semanticsDrawerVisible.value = true
  }

  function closeSemanticsDrawer() {
    semanticsDrawerVisible.value = false
  }

  function updateRelationSemanticInStore(sem: RelationSemanticInfo) {
    const idx = relationSemantics.value.findIndex(
      s => s.rel_type === sem.rel_type,
    )
    if (idx >= 0) {
      relationSemantics.value[idx] = sem
    } else {
      relationSemantics.value.push(sem)
    }
  }

  function removeRelationSemanticFromStore(relType: string) {
    relationSemantics.value = relationSemantics.value.filter(
      s => s.rel_type !== relType,
    )
  }

  function setCurrentSystem(systemId: string) {
    currentSystemId.value = systemId
    const sys = systemList.value.find(s => s.system_id === systemId)
    if (sys) currentSystemInfo.value = sys
  }

  function sortSystemsById(list: SystemInfo[]) {
    return [...list].sort((a, b) => a.id - b.id)
  }

  function setSystemList(list: SystemInfo[]) {
    systemList.value = sortSystemsById(list)
  }

  function addSystem(sys: SystemInfo) {
    const idx = systemList.value.findIndex(s => s.system_id === sys.system_id)
    if (idx >= 0) {
      systemList.value[idx] = sys
    } else {
      systemList.value.push(sys)
    }
    systemList.value = sortSystemsById(systemList.value)
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
    // v3.5: 重置所有向导状态
    importMode.value = 'new'
    appendTargetSystemId.value = ''
    newSystemPrefix.value = ''
    newSystemName.value = ''
    newSystemDesc.value = ''
    importStep.value = 0
    validationReport.value = null
    executeResult.value = null
    conflictStrategy.value = 'merge'
    lastSnapshotId.value = null
    importWizardVisible.value = true
  }

  function closeImportWizard() {
    importWizardVisible.value = false
    // v3.5: 重置步骤
    importStep.value = 0
    validationReport.value = null
    executeResult.value = null
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
    selectedTreeNode,
    treeRefreshKey,
    selectNode,
    selectRelationship,
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
    // v3.5
    importMode,
    appendTargetSystemId,
    newSystemPrefix,
    newSystemName,
    newSystemDesc,
    importStep,
    validationReport,
    executeResult,
    conflictStrategy,
    lastSnapshotId,
    editorLabels,
    // v3.6 关系语义
    relationSemantics,
    semanticsDrawerVisible,
    semanticsLoading,
    loadRelationSemantics,
    openSemanticsDrawer,
    closeSemanticsDrawer,
    updateRelationSemanticInStore,
    removeRelationSemanticFromStore,
  }
})
