<script setup lang="ts">
import { ref, watch, nextTick, h, onMounted, computed } from 'vue'
import {
  SendOutlined,
  SearchOutlined,
  InfoCircleOutlined,
  NodeIndexOutlined,
  EditOutlined,
  DeleteOutlined,
  SettingOutlined,
  LinkOutlined,
  QuestionCircleOutlined,
  PlusOutlined,
  SaveOutlined,
} from '@ant-design/icons-vue'
import { message, Modal, Drawer, Form, Input, Select, Button, Tag, Alert, Collapse, Space } from 'ant-design-vue'
import { useAppStore } from '@/stores'
import {
  fetchNodeDetail, postQuery, deleteEntity, checkEntityDeletion,
  fetchRelationship, deleteRelationship,
  upsertRelationSemantic, deleteRelationSemantic,
  fetchAvailableRelationshipTypes,
  fetchRelationshipInstances,
  searchNodes,
  checkRelationshipDuplicate,
  updateRelationshipFull,
  createRelationship,
} from '@/api'
import type {
  NodeDetail, QueryResponse, RelationshipResponse, DeletionCheckResult,
  RelationSemanticInfo, UpsertRelationSemanticRequest,
  RelationshipInstanceSummary,
} from '@/types'
import {
  CARDINALITY_OPTIONS, SYMMETRY_OPTIONS, TRANSITIVITY_OPTIONS,
} from '@/types'

const store = useAppStore()

const question = ref('')
const asking = ref(false)
const conversation = ref<Array<{ role: 'user' | 'ai'; content: string }>>([])
const conversationBodyRef = ref<HTMLElement | null>(null)

function scrollToBottom() {
  nextTick(() => {
    const el = conversationBodyRef.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

// 节点/关系详情相关
const detail = ref<NodeDetail | null>(null)
const relDetail = ref<RelationshipResponse | null>(null)
const detailLoading = ref(false)
const detailError = ref('')
const isCategoryNode = ref(false)
const isRelationNode = ref(false)
// 关系类型节点（左侧树点击关系类型 → 展示该类型下所有实例列表）
const isRelationTypeNode = ref(false)
const relInstances = ref<RelationshipInstanceSummary[]>([])
const relInstancesLoading = ref(false)

/** 关系类型短名（不含前缀），用于 API 调用。
 *  本体树 API 已剥离系统前缀（ontology_service.strip_prefix），
 *  node.name 即为短名称（如 HAS_SYMPTOM），直接使用即可。 */
const relTypeShortName = computed(() => {
  return store.selectedNode?.name || ''
})

// 监听选中节点，加载详情
watch(
  () => store.selectedNode,
  async (node) => {
    console.log('[QueryPanel] watch selectedNode:', JSON.stringify(node))
    if (!node) {
      detail.value = null
      relDetail.value = null
      detailError.value = ''
      isCategoryNode.value = false
      isRelationNode.value = false
      isRelationTypeNode.value = false
      relInstances.value = []
      return
    }

    // 关系元数据/根节点只展示摘要
    if (node.type === '__RELATIONSHIP_ROOT__' || node.type === '__REL_META__') {
      detail.value = null
      relDetail.value = null
      detailError.value = ''
      isCategoryNode.value = true
      isRelationNode.value = false
      isRelationTypeNode.value = false
      return
    }

    // 关系节点（左侧树中的关系类型）
    if (node.type === '__RELATIONSHIP__') {
      if (!node.elementId) {
        // 关系类型节点：加载该类型下所有实例列表（源实体→关系→目标实体）
        detail.value = null
        relDetail.value = null
        detailError.value = ''
        isCategoryNode.value = false
        isRelationNode.value = false
        isRelationTypeNode.value = true
        relInstances.value = []
        relInstancesLoading.value = true
        try {
          relInstances.value = await fetchRelationshipInstances(
            node.name,
            store.currentSystemId,
          )
        } catch (e: any) {
          detailError.value = e?.response?.data?.detail || '加载关系实例失败'
        } finally {
          relInstancesLoading.value = false
        }
        return
      }

      detail.value = null
      detailError.value = ''
      isCategoryNode.value = false
      isRelationNode.value = true
      isRelationTypeNode.value = false
      detailLoading.value = true
      try {
        relDetail.value = await fetchRelationship(node.elementId)
      } catch (e: any) {
        detailError.value = e?.response?.data?.detail || '加载关系详情失败'
        relDetail.value = null
      } finally {
        detailLoading.value = false
      }
      return
    }

    // 没有 elementId 的类型节点
    if (!node.elementId) {
      detail.value = null
      relDetail.value = null
      detailError.value = ''
      isCategoryNode.value = true
      isRelationNode.value = false
      isRelationTypeNode.value = false
      return
    }

    // 实体节点
    isCategoryNode.value = false
    isRelationNode.value = false
    isRelationTypeNode.value = false
    relDetail.value = null
    detailLoading.value = true
    detailError.value = ''
    try {
      detail.value = await fetchNodeDetail(node.elementId, store.currentSystemId)
    } catch (e: any) {
      detailError.value = e?.response?.data?.detail || '加载节点详情失败'
      detail.value = null
    } finally {
      detailLoading.value = false
    }
  },
  { immediate: true },
)

// 监听图谱边点击选中的关系，展示关系详情（源实体→关系→目标实体）
watch(
  () => store.selectedRelationship,
  (rel) => {
    if (rel) {
      // 图谱边被点击：设置关系详情，清空实体详情状态
      detail.value = null
      detailError.value = ''
      isCategoryNode.value = false
      isRelationNode.value = true
      relDetail.value = rel
      detailLoading.value = false
    } else if (!store.selectedNode) {
      // 关系选中被清空且无节点选中时，重置关系详情
      relDetail.value = null
      isRelationNode.value = false
    }
  },
)

// 监听系统切换：清除所有详情状态，防止旧系统数据残留
watch(
  () => store.currentSystemId,
  () => {
    relDetail.value = null
    isRelationNode.value = false
    detail.value = null
    detailError.value = ''
    isCategoryNode.value = false
    isRelTypeEditMode.value = false
    // 清除关系编辑相关残留状态
    editableInstances.value = []
    relInstances.value = []
    relTypeProperties.value = {}
    // 关闭关系编辑器并清除编辑状态
    store.closeRelationshipEditor()
  },
)

async function handleAsk() {
  const q = question.value.trim()
  if (!q) return
  if (asking.value) return

  asking.value = true
  conversation.value.push({ role: 'user', content: q })
  question.value = ''
  scrollToBottom()

  try {
    const res = await postQuery({ question: q, system_id: store.currentSystemId })
    conversation.value.push({ role: 'ai', content: res.answer })
    scrollToBottom()
  } catch (e: any) {
    const errMsg = e?.response?.data?.detail || '查询失败，请检查后端服务'
    message.error(errMsg)
    conversation.value.pop()
  } finally {
    asking.value = false
  }
}

// v2.0: 编辑当前选中实体或关系
function handleEdit() {
  // 如果选中的是关系类型节点 → 进入内联编辑模式
  if (isRelationTypeNode.value) {
    handleRelTypeEdit()
    return
  }

  // 如果选中的是关系详情（有具体 elementId）
  if (isRelationNode.value && relDetail.value) {
    store.openEditRelationshipEditor(relDetail.value)
    return
  }

  // 如果选中的是关系类型分类节点 → 打开新增关系面板（预填类型）
  if (isCategoryNode.value && store.selectedNode?.type === '__RELATIONSHIP__') {
    store.openCreateRelationshipWithType(store.selectedNode.name)
    return
  }

  if (!store.selectedNode || !store.selectedNode.elementId) {
    message.warning('请先在左侧树中点击选择一个实体或关系')
    return
  }
  if (!detail.value) return
  store.openEntityEditor('edit', {
    element_id: store.selectedNode.elementId,
    labels: [detail.value.type],
    name: detail.value.name,
    properties: Object.fromEntries(
      detail.value.properties.map((p) => [p.key, p.value]),
    ),
    relationship_count: detail.value.relationships.length,
  })
}

// v2.0: 删除当前选中实体或关系
async function handleDelete() {
  // 关系类型节点不支持直接删除（提示用户在编辑模式中逐条删除）
  if (isRelationTypeNode.value) {
    message.warning('关系类型节点不支持直接删除，请点击"编辑"进入编辑模式逐条删除关系实例')
    return
  }

  // 关系删除
  if (isRelationNode.value && relDetail.value) {
    const rel = relDetail.value
    Modal.confirm({
      title: `删除关系`,
      content: `确定要删除关系 "${rel.source_name} →[${rel.type}]→ ${rel.target_name}" 吗？`,
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      async onOk() {
        try {
          await deleteRelationship(rel.element_id)
          message.success('关系已删除')
          store.clearSelection()
          store.triggerTreeRefresh()
        } catch (err: any) {
          const detailMsg = err?.response?.data?.detail || '删除失败'
          message.error(typeof detailMsg === 'string' ? detailMsg : '删除失败')
        }
      },
    })
    return
  }

  // 实体删除：先校验
  if (!store.selectedNode) {
    message.warning('请先在左侧树中点击选择一个实体或关系')
    return
  }
  const node = store.selectedNode

  // 删除前校验：检查该节点是否有关联关系
  let checkResult: DeletionCheckResult
  try {
    checkResult = await checkEntityDeletion(node.elementId)
  } catch (err: any) {
    const detailMsg = err?.response?.data?.detail || '校验失败，请稍后重试'
    message.error(typeof detailMsg === 'string' ? detailMsg : '校验失败')
    return
  }

  if (!checkResult.can_delete) {
    // 存在关联关系，展示列表并让用户确认级联删除
    const relList = checkResult.relationships
    const relItems = relList.map(
      (r) => {
        const arrow = r.direction === 'outgoing' ? '→' : '←'
        const sourcePart = r.direction === 'outgoing' ? node.name : r.other_node_name
        const targetPart = r.direction === 'outgoing' ? r.other_node_name : node.name
        return `  • ${sourcePart} ${arrow}[${r.type}]${arrow} ${targetPart}`
      }
    ).join('\n')

    Modal.confirm({
      title: `删除 "${node.name}" 及其关联关系`,
      width: 560,
      content: h('div', null, [
        h('p', { style: { marginBottom: '12px', color: '#ff4d4f', fontWeight: 'bold' } },
          `该节点有 ${checkResult.relationship_count} 条关联关系，确认后将一并删除所有关联关系和该节点。`
        ),
        h('p', { style: { marginBottom: '8px' } }, '关联关系列表：'),
        h('pre', {
          style: {
            background: '#fafafa', padding: '8px 12px', borderRadius: '6px',
            fontSize: '13px', lineHeight: '1.8', maxHeight: '200px',
            overflowY: 'auto', marginBottom: '12px',
          },
        }, relItems),
      ]),
      okText: '确认全部删除',
      okType: 'danger',
      cancelText: '取消',
      async onOk() {
        try {
          await deleteEntity(node.elementId, true)
          message.success(`已删除实体"${node.name}"及 ${checkResult.relationship_count} 条关联关系`)
          store.clearSelection()
          store.triggerTreeRefresh()
        } catch (err: any) {
          const detailMsg = err?.response?.data?.detail || '删除失败'
          message.error(typeof detailMsg === 'string' ? detailMsg : '删除失败')
        }
      },
    })
    return
  }

  // 无关联关系，直接删除
  Modal.confirm({
    title: `删除 "${node.name}"`,
    content: `确定要删除实体"${node.name}"吗？此操作不可撤销。`,
    okText: '确认删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      try {
        await deleteEntity(node.elementId)
        message.success('删除成功')
        store.clearSelection()
        store.triggerTreeRefresh()
      } catch (err: any) {
        const detailMsg = err?.response?.data?.detail || '删除失败'
        message.error(typeof detailMsg === 'string' ? detailMsg : '删除失败')
      }
    },
  })
}

function handleKeyup(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleAsk()
  }
}

// ===== 关系类型节点 - 内联编辑 =====

const isRelTypeEditMode = ref(false)

interface EditableInstance {
  key: string
  elementId: string
  sourceId: string
  sourceName: string
  targetId: string
  targetName: string
  isDuplicate: boolean
  isEmpty: boolean
  isNew: boolean
  isDeleted: boolean
}

const editableInstances = ref<EditableInstance[]>([])
const entitySearchOptions = ref<Array<{ value: string; label: string }>>([])
let instanceKeyCounter = 0

/** 从当前可编辑实例中收集已选实体选项，防止搜索时丢失已选项的显示名称 */
function getExistingEntityOptions(): Map<string, { value: string; label: string }> {
  const map = new Map<string, { value: string; label: string }>()
  for (const inst of editableInstances.value) {
    if (inst.isDeleted) continue
    if (inst.sourceId && inst.sourceName) {
      map.set(inst.sourceId, { value: inst.sourceId, label: `${inst.sourceName}` })
    }
    if (inst.targetId && inst.targetName) {
      map.set(inst.targetId, { value: inst.targetId, label: `${inst.targetName}` })
    }
  }
  return map
}

async function handleEntitySearch(keyword: string): Promise<void> {
  // 始终保留已选实体的选项
  const merged = getExistingEntityOptions()

  if (keyword && keyword.length >= 1) {
    try {
      const results = await searchNodes(keyword, store.currentSystemId)
      for (const r of results) {
        merged.set(r.element_id, {
          value: r.element_id,
          label: `${r.name} (${r.label})`,
        })
      }
    } catch {
      // 搜索失败时仍保留已有选项
    }
  }

  entitySearchOptions.value = Array.from(merged.values())
}

async function checkInstanceDuplicate(inst: EditableInstance): Promise<void> {
  if (!inst.sourceId || !inst.targetId) {
    inst.isEmpty = !inst.sourceId || !inst.targetId
    inst.isDuplicate = false
    return
  }
  inst.isEmpty = false
  try {
    const result = await checkRelationshipDuplicate(
      inst.sourceId,
      inst.targetId,
      relTypeShortName.value,
      store.currentSystemId,
      inst.isNew ? '' : inst.elementId,
    )
    inst.isDuplicate = result.exists
  } catch {
    inst.isDuplicate = false
  }
}

function onSourceChange(inst: EditableInstance, option: { value: string; label: string } | undefined): void {
  inst.sourceId = option?.value || ''
  inst.sourceName = option?.label?.split(' (')[0] || ''
  checkInstanceDuplicate(inst)
}

function onTargetChange(inst: EditableInstance, option: { value: string; label: string } | undefined): void {
  inst.targetId = option?.value || ''
  inst.targetName = option?.label?.split(' (')[0] || ''
  checkInstanceDuplicate(inst)
}

async function handleRelTypeEdit(): Promise<void> {
  if (!isRelationTypeNode.value) return
  isRelTypeEditMode.value = true
  try {
    const instances = await fetchRelationshipInstances(
      relTypeShortName.value,
      store.currentSystemId,
    )
    editableInstances.value = instances.map(inst => ({
      key: `inst-${instanceKeyCounter++}`,
      elementId: inst.element_id,
      sourceId: inst.source_id,
      sourceName: inst.source_name,
      targetId: inst.target_id,
      targetName: inst.target_name,
      isDuplicate: false,
      isEmpty: false,
      isNew: false,
      isDeleted: false,
    }))
    // 预填充搜索选项，使 a-select 能正确显示已有实体的名称而非 elementId
    const existingOptions = new Map<string, { value: string; label: string }>()
    for (const inst of instances) {
      if (inst.source_id) {
        existingOptions.set(inst.source_id, {
          value: inst.source_id,
          label: `${inst.source_name} (${inst.source_label})`,
        })
      }
      if (inst.target_id) {
        existingOptions.set(inst.target_id, {
          value: inst.target_id,
          label: `${inst.target_name} (${inst.target_label})`,
        })
      }
    }
    entitySearchOptions.value = Array.from(existingOptions.values())
    // 加载关系属性
    loadRelTypeProperties()
  } catch (e: unknown) {
    message.error(`加载关系实例失败: ${getErrorMessage(e)}`)
  }
}

async function handleRelTypeSave(): Promise<void> {
  const activeInstances = editableInstances.value.filter(i => !i.isDeleted)

  // 校验空记录
  for (const inst of activeInstances) {
    if (!inst.sourceId || !inst.targetId) {
      message.error('源实体和目标实体不能为空，请补充完整后再保存')
      return
    }
  }

  // 校验重复
  for (const inst of activeInstances) {
    if (inst.isDuplicate) {
      message.error('存在重复的关系记录，请修改后再保存')
      return
    }
  }

  // 前端二次重复检查
  const seen = new Set<string>()
  for (const inst of activeInstances) {
    const key = `${inst.sourceId}|${inst.targetId}`
    if (seen.has(key)) {
      message.error('列表中存在重复的源实体-目标实体组合')
      return
    }
    seen.add(key)
  }

  try {
    // 删除标记的实例
    const toDelete = editableInstances.value.filter(i => i.isDeleted && !i.isNew)
    for (const inst of toDelete) {
      await deleteRelationship(inst.elementId)
    }

    // 更新修改的实例
    const toUpdate = activeInstances.filter(i => !i.isNew)
    for (const inst of toUpdate) {
      await updateRelationshipFull(inst.elementId, {
        source_element_id: inst.sourceId,
        target_element_id: inst.targetId,
      })
    }

    // 创建新实例
    const toCreate = activeInstances.filter(i => i.isNew)
    for (const inst of toCreate) {
      await createRelationship(
        {
          source_element_id: inst.sourceId,
          target_element_id: inst.targetId,
          type: relTypeShortName.value,
        },
        store.currentSystemId,
      )
    }

    message.success('保存成功')
    isRelTypeEditMode.value = false
    editableInstances.value = []
    await loadTree()
  } catch (e: unknown) {
    message.error(`保存失败: ${getErrorMessage(e)}`)
  }
}

function addNewInstance(): void {
  editableInstances.value.push({
    key: `new-${instanceKeyCounter++}`,
    elementId: '',
    sourceId: '',
    sourceName: '',
    targetId: '',
    targetName: '',
    isDuplicate: false,
    isEmpty: false,
    isNew: true,
    isDeleted: false,
  })
}

function deleteInstance(inst: EditableInstance): void {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除关系 "${inst.sourceName} → ${inst.targetName}" 吗？`,
    okText: '确认删除',
    okType: 'danger',
    cancelText: '取消',
    onOk() {
      if (inst.isNew) {
        editableInstances.value = editableInstances.value.filter(i => i.key !== inst.key)
      } else {
        inst.isDeleted = true
      }
    },
  })
}

// 关系属性管理
const relTypeProperties = ref<string[]>([])
const newRelPropKey = ref('')
const newRelPropValue = ref('')

function loadRelTypeProperties(): void {
  // 从已有实例中收集常见属性键
  const propKeys = new Set<string>()
  if (relDetail.value?.properties) {
    Object.keys(relDetail.value.properties).forEach(k => propKeys.add(k))
  }
  relTypeProperties.value = Array.from(propKeys)
}

function addRelProperty(): void {
  if (!newRelPropKey.value.trim()) {
    message.warning('请输入属性名')
    return
  }
  if (relTypeProperties.value.includes(newRelPropKey.value.trim())) {
    message.warning('该属性已存在')
    return
  }
  relTypeProperties.value.push(newRelPropKey.value.trim())
  newRelPropKey.value = ''
  newRelPropValue.value = ''
}

function removeRelProperty(key: string): void {
  relTypeProperties.value = relTypeProperties.value.filter(k => k !== key)
}

// ==================== v3.6 关系语义编辑 ====================

const semanticsDrawerVisible = ref(false)
const editingSemantic = ref<RelationSemanticInfo | null>(null)
const semForm = ref({
  rel_type: '',
  display_name: '',
  description: '',
  source_hint: '',
  target_hint: '',
  cardinality: '',
  symmetry: '',
  transitivity: '',
})
const semSaving = ref(false)
const semTypesLoading = ref(false)

/** 所有可用的关系类型（从 Neo4j 加载） */
const allRelTypes = ref<string[]>([])
const selectedRelType = ref<string | undefined>(undefined)

/** 下拉搜索过滤 */
function filterRelTypes(input: string, option: any): boolean {
  const label = (option.label || '').toLowerCase()
  const value = (option.value || '').toLowerCase()
  const q = input.toLowerCase()
  return label.includes(q) || value.includes(q)
}

/** 下拉选项列表：标记已配置 vs 未配置 */
const relTypeOptions = computed(() =>
  allRelTypes.value.map(type => {
    const hasSemantics = store.relationSemantics.some(s => s.rel_type === type)
    return {
      value: type,
      label: type,
      title: `${type}${hasSemantics ? ' (已配置)' : ''}`,
    }
  })
)

/** 文本域自适应高度 */
function resizeTextarea(e: Event) {
  const el = e.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = el.scrollHeight + 'px'
}

/** 加载所有可用的关系类型 */
async function loadAllRelTypes() {
  semTypesLoading.value = true
  try {
    const res = await fetchAvailableRelationshipTypes(store.currentSystemId)
    allRelTypes.value = res.relationship_types
  } catch {
    allRelTypes.value = []
  } finally {
    semTypesLoading.value = false
  }
}

/** 打开语义编辑 Drawer */
function openSemanticsDrawer() {
  store.openSemanticsDrawer()
  semanticsDrawerVisible.value = true
  selectedRelType.value = undefined
  editingSemantic.value = null
  loadAllRelTypes()
}

/** 从下拉框选择关系类型 */
function onRelTypeSelect(value: string) {
  selectedRelType.value = value
  const existing = store.relationSemantics.find(s => s.rel_type === value)
  if (existing) {
    editingSemantic.value = existing
    semForm.value = {
      rel_type: existing.rel_type,
      display_name: existing.display_name,
      description: existing.description,
      source_hint: existing.source_hint,
      target_hint: existing.target_hint,
      cardinality: existing.cardinality,
      symmetry: existing.symmetry,
      transitivity: existing.transitivity,
    }
  } else {
    editingSemantic.value = null
    semForm.value = {
      rel_type: value,
      display_name: '',
      description: '',
      source_hint: '',
      target_hint: '',
      cardinality: '',
      symmetry: '',
      transitivity: '',
    }
  }
  // 下一帧调整文本域高度
  nextTick(() => {
    const textareas = document.querySelectorAll('.sem-form-textarea')
    textareas.forEach(el => {
      const ta = el as HTMLTextAreaElement
      ta.style.height = 'auto'
      ta.style.height = ta.scrollHeight + 'px'
    })
  })
}

/** 保存语义 */
async function saveSemantic() {
  if (!semForm.value.rel_type.trim()) {
    message.warning('请先选择关系类型')
    return
  }
  semSaving.value = true
  try {
    const req: UpsertRelationSemanticRequest = {
      rel_type: semForm.value.rel_type.trim(),
      display_name: semForm.value.display_name.trim(),
      description: semForm.value.description.trim(),
      source_hint: semForm.value.source_hint.trim(),
      target_hint: semForm.value.target_hint.trim(),
      cardinality: semForm.value.cardinality,
      symmetry: semForm.value.symmetry,
      transitivity: semForm.value.transitivity,
    }
    const result = await upsertRelationSemantic(
      store.currentPrefix,
      req.rel_type,
      req,
    )
    store.updateRelationSemanticInStore(result)
    message.success('语义已保存')
    editingSemantic.value = result
  } catch {
    message.error('保存失败')
  } finally {
    semSaving.value = false
  }
}

/** 删除语义 */
async function removeSemantic(relType: string) {
  Modal.confirm({
    title: '删除语义说明',
    content: `确定要删除 "${relType}" 的语义说明吗？删除后该关系在查询时将使用默认名称。`,
    okText: '确认删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      try {
        await deleteRelationSemantic(store.currentPrefix, relType)
        store.removeRelationSemanticFromStore(relType)
        if (editingSemantic.value?.rel_type === relType) {
          editingSemantic.value = null
        }
        message.success('已删除')
      } catch {
        message.error('删除失败')
      }
    },
  })
}

/** 在关系详情中快速编辑语义 */
function openSemanticFromRelDetail(relType: string) {
  openSemanticsDrawer()
  // 等待抽屉打开 + 类型列表加载后选中
  nextTick(() => {
    selectedRelType.value = relType
    onRelTypeSelect(relType)
  })
}

/** 监听系统切换时重新加载语义 */
watch(
  () => store.currentPrefix,
  async (prefix) => {
    if (prefix) {
      await store.loadRelationSemantics(prefix)
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="query-panel">
    <!-- 节点详情区域 -->
    <div class="panel-section detail-section">
      <div class="panel-header">
        <InfoCircleOutlined />
        <span>详情</span>
        <a-spin v-if="detailLoading" size="small" />

        <!-- v2.0: 编辑按钮（实体或关系均可编辑） -->
        <template v-if="isRelTypeEditMode">
          <a-button type="primary" size="small" class="header-action-btn" @click="handleRelTypeSave">
            <SaveOutlined /> 保存
          </a-button>
          <a-button type="default" size="small" class="header-action-btn" @click="isRelTypeEditMode = false">
            取消
          </a-button>
        </template>
        <template v-else>
          <a-button type="default" size="small" class="header-action-btn header-action-edit" @click="handleEdit">
            <EditOutlined /> 编辑
          </a-button>
          <a-button
            type="default"
            size="small"
            class="header-action-btn header-action-danger"
            @click="handleDelete"
          >
            <DeleteOutlined /> 删除
          </a-button>
        </template>
      </div>
      <div class="detail-body">
        <template v-if="!store.selectedNode && !store.selectedRelationship">
          <a-empty description="点击左侧本体树、图谱节点或关系查看详情" :image-style="{ height: '40px' }" />
        </template>
        <template v-else-if="detailLoading">
          <div class="detail-loading">
            <a-spin size="small" />
            <span style="margin-left: 8px; color: #999; font-size: 13px;">加载中...</span>
          </div>
        </template>
        <template v-else-if="isCategoryNode">
          <div class="detail-node-name">{{ store.selectedNode.name }}</div>
          <a-tag>{{ store.selectedNode.type }}</a-tag>
          <a-divider style="margin: 12px 0" />
          <div class="sub-title">摘要</div>
          <p style="color: #666; font-size: 13px;">这是一个节点分类，请展开子项查看具体实体详情。</p>
        </template>
        <template v-else-if="detailError">
          <a-alert :message="detailError" type="error" show-icon />
        </template>

        <!-- 关系类型节点：展示该类型下所有实例列表（可编辑） -->
        <template v-else-if="isRelationTypeNode">
          <div class="detail-node-name">{{ store.selectedNode?.name }}</div>
          <a-tag color="blue">关系类型</a-tag>
          <span v-if="!relInstancesLoading && relInstances.length > 0" class="rel-instance-count">
            共 {{ relInstances.length }} 条实例
          </span>
          <a-divider style="margin: 12px 0" />

          <div v-if="relInstancesLoading" class="detail-loading">
            <a-spin size="small" />
            <span style="margin-left: 8px; color: #999; font-size: 13px;">加载实例中...</span>
          </div>

          <template v-else>
            <!-- 编辑模式 -->
            <template v-if="isRelTypeEditMode">
              <div class="rel-edit-list">
                <div
                  v-for="inst in editableInstances.filter(i => !i.isDeleted)"
                  :key="inst.key"
                  class="rel-edit-row"
                  :class="{ 'rel-edit-row-error': inst.isDuplicate || inst.isEmpty }"
                >
                  <a-select
                    show-search
                    size="small"
                    popup-class-name="rel-edit-select-popup"
                    :value="inst.sourceId || undefined"
                    placeholder="搜索源实体..."
                    style="flex: 1; min-width: 0"
                    :filter-option="false"
                    :options="entitySearchOptions"
                    @search="handleEntitySearch"
                    @change="(_val: string, option: any) => onSourceChange(inst, option)"
                    allow-clear
                  />
                  <span class="rel-edit-arrow">→</span>
                  <a-tag color="blue" class="rel-edit-type-tag">{{ relTypeShortName }}</a-tag>
                  <span class="rel-edit-arrow">→</span>
                  <a-select
                    show-search
                    size="small"
                    popup-class-name="rel-edit-select-popup"
                    :value="inst.targetId || undefined"
                    placeholder="搜索目标实体..."
                    style="flex: 1; min-width: 0"
                    :filter-option="false"
                    :options="entitySearchOptions"
                    @search="handleEntitySearch"
                    @change="(_val: string, option: any) => onTargetChange(inst, option)"
                    allow-clear
                  />
                  <a-button
                    type="text"
                    danger
                    size="small"
                    @click="deleteInstance(inst)"
                  >
                    <DeleteOutlined />
                  </a-button>
                </div>
                <div v-if="editableInstances.filter(i => !i.isDeleted).some(i => i.isDuplicate)" class="rel-edit-error">
                  存在重复的关系记录，请修改后再保存
                </div>
                <div v-if="editableInstances.filter(i => !i.isDeleted).some(i => i.isEmpty)" class="rel-edit-error">
                  源实体和目标实体不能为空
                </div>
                <a-button type="dashed" block @click="addNewInstance" style="margin-top: 8px">
                  <PlusOutlined /> 添加新关系
                </a-button>
              </div>

              <!-- 关系属性管理 -->
              <div class="rel-props-section">
                <div class="sub-title">
                  关系属性
                  <span class="sub-title-hint">（可添加到该类型的所有关系实例）</span>
                </div>
                <div v-if="relTypeProperties.length > 0" class="rel-props-list">
                  <div v-for="propKey in relTypeProperties" :key="propKey" class="rel-prop-item">
                    <span class="rel-prop-key">{{ propKey }}</span>
                    <a-button type="text" danger size="small" @click="removeRelProperty(propKey)">
                      <DeleteOutlined />
                    </a-button>
                  </div>
                </div>
                <div class="rel-prop-add-row">
                  <a-input
                    v-model:value="newRelPropKey"
                    placeholder="属性名"
                    size="small"
                    style="flex: 1"
                  />
                  <a-button size="small" type="dashed" @click="addRelProperty">
                    <PlusOutlined /> 添加
                  </a-button>
                </div>
              </div>
            </template>

            <!-- 只读模式 -->
            <template v-else>
              <div v-if="relInstances.length > 0" class="rel-instances-list">
                <div
                  v-for="(inst, idx) in relInstances"
                  :key="inst.element_id || idx"
                  class="rel-instance-row"
                >
                  <span class="rel-name">{{ inst.source_name }}</span>
                  <span class="rel-arrow">→</span>
                  <span class="rel-type">{{ store.selectedNode?.name }}</span>
                  <span class="rel-arrow">→</span>
                  <span class="rel-name">{{ inst.target_name }}</span>
                </div>
              </div>
              <a-empty v-else description="该关系类型暂无实例" :image-style="{ height: '30px' }" />
            </template>
          </template>
        </template>

        <!-- v2.0: 关系详情展示（左侧树关系类型 或 图谱边点击） -->
        <template v-else-if="(isRelationNode || store.selectedRelationship) && relDetail">
          <div class="detail-rel-header">
            <span class="detail-rel-source">{{ relDetail.source_name }}</span>
            <span class="detail-rel-arrow">→</span>
            <a-tag color="blue">{{ relDetail.type }}</a-tag>
            <span class="detail-rel-arrow">→</span>
            <span class="detail-rel-target">{{ relDetail.target_name }}</span>
          </div>
          <a-divider style="margin: 12px 0" />

          <!-- v3.6: 关系语义说明（可编辑） -->
          <div class="semantic-inline">
            <div class="sub-title">
              语义说明
              <a-button
                type="link"
                size="small"
                @click="openSemanticFromRelDetail(relDetail.type)"
              >
                <EditOutlined /> {{ store.relationSemantics.find(s => s.rel_type === relDetail.type) ? '编辑' : '添加' }}
              </a-button>
            </div>
            <template v-if="store.relationSemantics.find(s => s.rel_type === relDetail.type)">
              <div class="semantic-tags">
                <a-tag v-if="store.relationSemantics.find(s => s.rel_type === relDetail.type)?.display_name"
                       color="green">
                  {{ store.relationSemantics.find(s => s.rel_type === relDetail.type)?.display_name }}
                </a-tag>
                <a-tag v-if="store.relationSemantics.find(s => s.rel_type === relDetail.type)?.cardinality"
                       color="blue">
                  {{ CARDINALITY_OPTIONS.find(o => o.value ===
                     store.relationSemantics.find(s => s.rel_type === relDetail.type)?.cardinality)?.label }}
                </a-tag>
              </div>
              <p v-if="store.relationSemantics.find(s => s.rel_type === relDetail.type)?.description"
                 class="semantic-desc">
                {{ store.relationSemantics.find(s => s.rel_type === relDetail.type)?.description }}
              </p>
            </template>
            <p v-else class="semantic-desc" style="color: #bfbfbf;">
              暂无语义说明，点击「添加」完善此关系的语义描述。
            </p>
          </div>

          <a-divider style="margin: 12px 0" />

          <!-- 关系属性 -->
          <div v-if="relDetail.properties && Object.keys(relDetail.properties).length > 0" class="detail-props">
            <div class="sub-title">属性</div>
            <div v-for="(val, key) in relDetail.properties" :key="key" class="prop-row">
              <span class="prop-key">{{ key }}</span>
              <span class="prop-value">{{ val }}</span>
            </div>
          </div>
          <a-empty v-else description="该关系无属性" :image-style="{ height: '30px' }" />
        </template>

        <!-- 实体详情展示 -->
        <template v-else-if="detail">
          <div class="detail-node-name">{{ detail.name }}</div>
          <a-tag :color="detail.type === 'Disease' ? 'red' : 'blue'">{{ detail.type }}</a-tag>
          <a-divider style="margin: 12px 0" />

          <div v-if="detail.properties.length > 0" class="detail-props">
            <div class="sub-title">属性</div>
            <div v-for="prop in detail.properties" :key="prop.key" class="prop-row">
              <span class="prop-key">{{ prop.key }}</span>
              <span class="prop-value">{{ prop.value }}</span>
            </div>
          </div>

          <div v-if="detail.relationships.length > 0" class="detail-relations">
            <div class="sub-title">关系 ({{ detail.relationships.length }})</div>
            <div
              v-for="rel in detail.relationships"
              :key="`${rel.type}-${rel.targetName}-${rel.direction}`"
              class="rel-row"
              @click="store.selectNode(rel.targetType, rel.targetName, rel.targetElementId || '')"
            >
              <span class="rel-name" :class="{ 'rel-current': rel.direction === 'out' }">
                {{ rel.direction === 'out' ? detail.name : rel.targetName }}
              </span>
              <span class="rel-arrow">→</span>
              <span class="rel-type">{{ rel.type }}</span>
              <span class="rel-arrow">→</span>
              <span class="rel-name" :class="{ 'rel-current': rel.direction === 'in' }">
                {{ rel.direction === 'out' ? rel.targetName : detail.name }}
              </span>
            </div>
          </div>
        </template>
        <template v-else>
          <a-empty description="暂无数据" :image-style="{ height: '30px' }" />
        </template>
      </div>
    </div>

    <!-- 图谱知识查询 -->
    <div class="panel-section query-section">
      <div class="panel-header">
        <SearchOutlined />
        <span>图谱知识查询</span>
        <a-button
          type="link"
          size="small"
          class="header-action-semantics"
          @click="openSemanticsDrawer"
        >
          <SettingOutlined /> 对关系进行语义说明
        </a-button>
      </div>
      <div class="query-body">
        <div class="input-area">
          <a-textarea
            v-model:value="question"
            placeholder="输入自然语言问题，例如: '感冒有什么症状?'"
            :auto-size="{ minRows: 2, maxRows: 6 }"
            @keyup="handleKeyup"
          />
          <a-button
            type="primary"
            :loading="asking"
            @click="handleAsk"
            :disabled="!question.trim()"
          >
            <template #icon><SendOutlined /></template>
          </a-button>
        </div>
        <div ref="conversationBodyRef" class="conversation-body">
          <div
            v-for="(msg, idx) in conversation"
            :key="idx"
            class="chat-msg"
            :class="msg.role === 'user' ? 'msg-user' : 'msg-ai'"
          >
            <div class="msg-content">{{ msg.content }}</div>
          </div>
          <div v-if="asking" class="chat-msg msg-ai">
            <div class="msg-content typing">思考中...</div>
          </div>
        </div>
      </div>
    </div>

    <!-- v3.6: 关系语义编辑 Drawer -->
    <Drawer
      title="关系语义说明"
      :open="semanticsDrawerVisible"
      :width="520"
      @close="semanticsDrawerVisible = false"
      :destroyOnClose="false"
    >
      <div class="semantics-drawer-content">
        <!-- 关系类型下拉选择 -->
        <div class="sem-select-area">
          <a-spin :spinning="semTypesLoading" size="small">
            <Select
              v-model:value="selectedRelType"
              show-search
              placeholder="搜索并选择要编辑的关系类型..."
              :filter-option="filterRelTypes"
              :options="relTypeOptions"
              size="large"
              style="width: 100%;"
              @select="onRelTypeSelect"
              @clear="selectedRelType = undefined; editingSemantic = null"
              allow-clear
            />
          </a-spin>
        </div>

        <!-- 编辑表单（选中关系类型后才展示） -->
        <div class="sem-edit-area" v-if="selectedRelType">
          <a-divider style="margin: 12px 0;" />
          <div class="sem-edit-header">
            <span class="sem-edit-title">
              {{ editingSemantic ? '编辑语义' : '新增语义' }}：<strong>{{ selectedRelType }}</strong>
            </span>
            <a-button
              v-if="editingSemantic"
              type="link"
              danger
              size="small"
              @click="removeSemantic(selectedRelType)"
            >
              <DeleteOutlined /> 删除
            </a-button>
          </div>
          <Form layout="vertical" :model="semForm" size="small">
            <Form.Item label="显示名称">
              <Input
                v-model:value="semForm.display_name"
                placeholder="如: 治疗"
              />
            </Form.Item>
            <Form.Item label="语义描述">
              <Input.TextArea
                v-model:value="semForm.description"
                placeholder="描述这个关系的语义含义..."
                class="sem-form-textarea"
                :rows="2"
                @input="resizeTextarea"
              />
            </Form.Item>
            <Form.Item label="典型源实体标签">
              <Input
                v-model:value="semForm.source_hint"
                placeholder="如: Drug"
              />
            </Form.Item>
            <Form.Item label="典型目标实体标签">
              <Input
                v-model:value="semForm.target_hint"
                placeholder="如: Disease"
              />
            </Form.Item>
            <Form.Item label="映射基数">
              <Select
                v-model:value="semForm.cardinality"
                :options="CARDINALITY_OPTIONS"
                placeholder="选择基数关系"
                allow-clear
              />
            </Form.Item>
            <Form.Item label="对称性">
              <Select
                v-model:value="semForm.symmetry"
                :options="SYMMETRY_OPTIONS"
                placeholder="选择对称性"
                allow-clear
              />
            </Form.Item>
            <Form.Item label="传递性">
              <Select
                v-model:value="semForm.transitivity"
                :options="TRANSITIVITY_OPTIONS"
                placeholder="选择传递性"
                allow-clear
              />
            </Form.Item>
            <Form.Item>
              <Button
                type="primary"
                :loading="semSaving"
                @click="saveSemantic"
                block
              >
                保存语义
              </Button>
            </Form.Item>
          </Form>
        </div>

        <!-- 未选择时的提示 -->
        <div v-else class="sem-empty-hint">
          <a-alert
            type="info"
            show-icon
            message="请在上方下拉菜单中选择需要编辑语义说明的关系类型"
            style="margin-top: 16px;"
          />
        </div>

        <!-- 优秀案例（折叠） -->
        <div class="semantics-example-area">
          <a-divider />
          <Collapse :bordered="false">
            <template #expandIcon>
              <QuestionCircleOutlined style="color: #1677ff" />
            </template>
            <template #header>
              <span style="font-weight: 600; font-size: 13px;">优秀语义说明案例</span>
            </template>
            <div class="example-list">
              <!-- 案例1 -->
              <div class="example-card">
                <div style="font-weight: 600; margin-bottom: 6px;">案例1：副作用关系</div>
                <p><strong>原名:</strong> HAS_SIDE_EFFECT</p>
                <p><strong>显示名:</strong> 副作用</p>
                <p><strong>描述:</strong> 药物产生某副作用的关系，表示服药后可能引发该副作用。</p>
                <p><strong>基数:</strong> 多对多 (一种药物可能产生多种副作用，一个副作用可能由多种药物引发)</p>
                <p><strong>对称性:</strong> 非对称 (副作用不会反过来作用于药物)</p>
                <p><strong>传递性:</strong> 非传递 (阿司匹林→胃痛, 胃痛→无法入睡，不代表阿司匹林→无法入睡)</p>
              </div>

              <!-- 案例2 -->
              <div class="example-card">
                <div style="font-weight: 600; margin-bottom: 6px;">案例2：归属关系</div>
                <p><strong>原名:</strong> BELONGS_TO</p>
                <p><strong>显示名:</strong> 归属</p>
                <p><strong>描述:</strong> 子分类归属于父分类的关系。表示子类是父类的一个分支。</p>
                <p><strong>基数:</strong> 多对一 (多个子类归属于一个父类)</p>
                <p><strong>对称性:</strong> 非对称 (归属是单向的)</p>
                <p><strong>传递性:</strong> 传递 (A属B, B属C → A属C)</p>
              </div>

              <a-divider />

              <div style="font-size: 12px; color: #666; line-height: 1.8;">
                <strong>💡 填写指南：</strong><br />
                • <strong>语义含义:</strong> 用自然语言描述这个关系代表什么。<br />
                • <strong>映射基数:</strong> 说明关系是 1:1, 1:N 还是 M:N。<br />
                • <strong>对称性:</strong> 如果 A→B 能推出 B→A，则为对称。<br />
                • <strong>传递性:</strong> 如果 A→B 且 B→C 能推出 A→C，则为传递。<br />
                • 完善的语义说明能显著提升 AI 查询的准确率。
              </div>
            </div>
          </Collapse>
        </div>
      </div>
    </Drawer>
  </div>
</template>

<style scoped>
.query-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-section {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.detail-section {
  flex: 1;
  border-bottom: 1px solid #e8e8e8;
  background: #fff;
}

.query-section {
  height: 55%;
  min-height: 280px;
  overflow: hidden;
  background: #fff;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 600;
  color: #262626;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
  background: #fafafa;
  flex-wrap: wrap;
  overflow: visible;
}

.panel-header :deep(.anticon) {
  color: #1890ff;
  font-size: 14px;
}

/* v2.0: 详情头部操作按钮 */
.header-action-btn {
  margin-left: 4px;
  font-size: 12px;
  height: 26px;
  padding: 0 10px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.header-action-edit {
  color: #1677ff;
  border-color: #1677ff;
}
.header-action-edit:hover {
  color: #fff !important;
  background: #1677ff !important;
  border-color: #1677ff !important;
}

.header-action-link {
  color: #52c41a;
  border-color: #52c41a;
}
.header-action-link:hover {
  color: #fff !important;
  background: #52c41a !important;
  border-color: #52c41a !important;
}

.header-action-danger {
  color: #ff4d4f;
  border-color: #ff4d4f;
}
.header-action-danger:hover {
  color: #fff !important;
  background: #ff4d4f !important;
  border-color: #ff4d4f !important;
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;
  background: #fff;
}

.detail-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
}

.detail-node-name {
  font-size: 18px;
  font-weight: 700;
  color: #262626;
  margin-bottom: 6px;
  line-height: 1.4;
}

/* v2.0: 关系详情头部 */
.detail-rel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 15px;
  font-weight: 600;
  color: #262626;
}

.detail-rel-source,
.detail-rel-target {
  color: #1677ff;
  cursor: pointer;
}

.detail-rel-arrow {
  color: #bfbfbf;
  font-size: 16px;
}

.sub-title {
  font-size: 11px;
  font-weight: 600;
  color: #8c8c8c;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 12px 0 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid #f5f5f5;
}

.prop-row {
  display: flex;
  justify-content: space-between;
  padding: 5px 0;
  border-bottom: 1px solid #fafafa;
  font-size: 13px;
  transition: background 0.15s;
}

.prop-row:hover {
  background: #fafafa;
}

.prop-key {
  color: #8c8c8c;
  flex-shrink: 0;
  margin-right: 12px;
}

.prop-value {
  color: #262626;
  text-align: right;
  word-break: break-all;
}

.rel-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  margin: 2px 0;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  background: #fafafa;
  border: 1px solid transparent;
  transition: all 0.2s;
}

.rel-row:hover {
  background: #e6f7ff;
  border-color: #91d5ff;
}

.rel-type {
  color: #1890ff;
  font-weight: 600;
  font-size: 11px;
  background: #e6f7ff;
  padding: 1px 6px;
  border-radius: 3px;
}

.rel-arrow {
  color: #bfbfbf;
}

.rel-name {
  color: #262626;
  font-weight: 500;
}

.rel-current {
  color: #1677ff;
  font-weight: 600;
}

/* 关系类型实例列表 */
.rel-instance-count {
  margin-left: 8px;
  color: #999;
  font-size: 12px;
}

.rel-instances-list {
  max-height: 400px;
  overflow-y: auto;
}

.rel-instance-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  margin: 2px 0;
  border-radius: 4px;
  font-size: 12px;
  background: #fafafa;
  border: 1px solid transparent;
  transition: all 0.2s;
}

.rel-instance-row:hover {
  background: #e6f7ff;
  border-color: #91d5ff;
}

/* 关系编辑行 */
.rel-edit-list {
  margin-bottom: 12px;
}

.rel-edit-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  margin: 4px 0;
  border-radius: 4px;
  background: #fafafa;
  border: 1px solid #f0f0f0;
  transition: all 0.2s;
}

.rel-edit-row:hover {
  background: #f5f5f5;
}

.rel-edit-row-error {
  border-color: #ff4d4f !important;
  background: #fff2f0 !important;
}

.rel-edit-arrow {
  color: #999;
  font-size: 12px;
  flex-shrink: 0;
}

.rel-edit-type-tag {
  flex-shrink: 0;
  margin-right: 0;
  font-size: 12px;
  line-height: 18px;
  padding: 0 4px;
}

/* 关系编辑行内 a-select 紧凑样式 */
.rel-edit-row :deep(.ant-select) {
  font-size: 12px;
}

.rel-edit-row :deep(.ant-select-selector) {
  min-height: 24px !important;
  padding: 0 8px !important;
}

.rel-edit-row :deep(.ant-select-selection-item) {
  line-height: 22px !important;
  font-size: 12px;
}

.rel-edit-row :deep(.ant-select-selection-placeholder) {
  line-height: 22px !important;
  font-size: 12px;
}

.rel-edit-row :deep(.ant-select-arrow) {
  font-size: 10px;
}

.rel-edit-error {
  color: #ff4d4f;
  font-size: 12px;
  margin-top: 4px;
  padding: 4px 8px;
  background: #fff2f0;
  border-radius: 4px;
}

/* 关系属性管理 */
.rel-props-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.rel-props-list {
  margin: 8px 0;
}

.rel-prop-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px;
  margin: 2px 0;
  background: #fafafa;
  border-radius: 4px;
  font-size: 12px;
}

.rel-prop-key {
  color: #1890ff;
  font-weight: 500;
}

.rel-prop-add-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

/* 查询区域布局 */
.query-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.input-area {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  background: #fff;
  flex-shrink: 0;
  width: 100%;
}

.input-area :deep(textarea.ant-input) {
  resize: vertical;
  min-height: 72px !important;
  height: 72px !important;
  font-size: 14px;
  line-height: 1.6;
}

.input-area :deep(.ant-btn) {
  flex-shrink: 0;
}

.conversation-body {
  flex: 1;
  min-height: 0;
  width: 100%;
  overflow-y: auto;
  padding: 12px 16px;
  background: #fafafa;
  border-top: 1px solid #f0f0f0;
}

.chat-msg {
  margin-bottom: 10px;
}

.msg-content {
  display: inline-block;
  max-width: 85%;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-user {
  text-align: right;
}

.msg-user .msg-content {
  background: #1890ff;
  color: #fff;
  border-radius: 12px 12px 4px 12px;
}

.msg-ai .msg-content {
  background: #fff;
  color: #262626;
  border: 1px solid #e8e8e8;
  border-radius: 12px 12px 12px 4px;
}

.typing {
  color: #bfbfbf;
  font-style: italic;
}

/* ==================== v3.6 语义相关样式 ==================== */

.header-action-semantics {
  margin-left: auto;
  color: #1677ff;
  font-size: 12px;
  padding: 0 8px;
}

.semantic-inline {
  margin: 8px 0;
}

.semantic-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin: 4px 0;
}

.semantic-desc {
  font-size: 12px;
  color: #666;
  margin: 4px 0 0;
  line-height: 1.6;
}

.semantics-drawer-content {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.sem-select-area {
  margin-bottom: 0;
}

.sem-edit-area {
  flex: 1;
}

.sem-edit-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.sem-edit-title {
  font-size: 14px;
  color: #333;
}

.sem-empty-hint {
  margin-bottom: 8px;
}

.semantics-example-area {
  margin-top: 20px;
  padding-top: 0;
}

.example-list {
  font-size: 13px;
}

.example-card {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 10px;
}

.example-card p {
  margin: 2px 0;
  font-size: 12px;
  line-height: 1.6;
  color: #333;
}
</style>

<style>
/* 关系编辑下拉弹窗紧凑样式（全局，因为弹窗 teleport 到 body） */
.rel-edit-select-popup .ant-select-item {
  font-size: 12px;
  line-height: 20px;
  padding: 2px 8px;
}

.rel-edit-select-popup .ant-select-item-option-content {
  font-size: 12px;
}
</style>
