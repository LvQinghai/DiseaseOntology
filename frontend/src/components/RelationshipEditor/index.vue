<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  LinkOutlined,
  SwapOutlined,
  PlusOutlined,
  DeleteOutlined,
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { useAppStore } from '@/stores'
import {
  createRelationship,
  updateRelationshipFull,
  searchNodes,
  fetchAvailableRelationshipTypes,
  fetchRelationshipInstances,
} from '@/api'
import type { RelationshipInstanceSummary } from '@/types'

const store = useAppStore()

const visible = computed({
  get: () => store.relationshipEditorVisible,
  set: (val) => {
    if (!val) store.closeRelationshipEditor()
  },
})

const isEdit = computed(() => store.relationshipEditorMode === 'edit')

const title = computed(() => {
  if (isEdit.value) {
    const rel = store.editingRelationship
    return `编辑关系: ${rel?.source_name || ''} → ${rel?.type || ''} → ${rel?.target_name || ''}`
  }
  return '新增关系'
})

// 表单
const form = ref({
  sourceId: '',
  sourceName: '',
  targetId: '',
  targetName: '',
  type: '',
})

const properties = ref<Array<{ key: string; value: string }>>([])
const saving = ref(false)

// 关系实例列表（编辑模式下展示当前类型的所有源→目标对）
const instances = ref<RelationshipInstanceSummary[]>([])
const loadingInstances = ref(false)

// 元数据
const relationshipTypeOptions = ref<Array<{ value: string; label: string }>>([])
const loadingTypes = ref(false)

// 节点搜索 - 本地列表 + 客户端实时筛选
const allNodes = ref<Array<{ value: string; label: string; name: string }>>([])
const loadingNodes = ref(false)

async function loadAllNodes() {
  if (loadingNodes.value) return
  loadingNodes.value = true
  try {
    const results = await searchNodes('', store.currentSystemId)
    allNodes.value = results.map((node) => ({
      value: node.element_id,
      label: `${node.name} [${node.labels.join(', ')}]`,
      name: node.name,
    }))
  } catch {
    allNodes.value = []
  } finally {
    loadingNodes.value = false
  }
}

// 本地筛选函数（大小写不敏感）
function filterNodeOption(input: string, option: any) {
  const text = (option.label || '').toString().toLowerCase()
  return text.includes(input.toLowerCase())
}

async function loadTypes() {
  loadingTypes.value = true
  try {
    const { relationship_types } = await fetchAvailableRelationshipTypes(store.currentSystemId)
    relationshipTypeOptions.value = relationship_types.map((t) => ({
      value: t,
      label: t,
    }))
  } catch {
    relationshipTypeOptions.value = []
  } finally {
    loadingTypes.value = false
  }
}

async function loadInstances() {
  const rel = store.editingRelationship
  if (!rel) return
  loadingInstances.value = true
  try {
    instances.value = await fetchRelationshipInstances(rel.type, store.currentSystemId)
  } catch {
    instances.value = []
  } finally {
    loadingInstances.value = false
  }
}

function handleSelectSource(_value: string, option: any) {
  form.value.sourceName = option.name || option.label
}

function handleSelectTarget(_value: string, option: any) {
  form.value.targetName = option.name || option.label
}

function swapSourceTarget() {
  const tmpId = form.value.sourceId
  const tmpName = form.value.sourceName
  form.value.sourceId = form.value.targetId
  form.value.sourceName = form.value.targetName
  form.value.targetId = tmpId
  form.value.targetName = tmpName
}

function addProperty() {
  properties.value.push({ key: '', value: '' })
}

function removeProperty(index: number) {
  properties.value.splice(index, 1)
}

function initFromData() {
  if (isEdit.value && store.editingRelationship) {
    const rel = store.editingRelationship
    form.value.sourceId = rel.source_id
    form.value.sourceName = rel.source_name
    form.value.targetId = rel.target_id
    form.value.targetName = rel.target_name
    form.value.type = rel.type
    properties.value = Object.entries(rel.properties || {}).map(([k, v]) => ({
      key: k,
      value: String(v),
    }))
  } else {
    form.value.sourceId = store.editingRelationshipSourceId
    form.value.sourceName = store.editingRelationshipSourceName
    form.value.targetId = ''
    form.value.targetName = ''
    form.value.type = store.presetRelationshipType || ''
    properties.value = []
  }
}

watch(visible, (val) => {
  if (val) {
    loadAllNodes()
    loadTypes()
    initFromData()
    if (isEdit.value) {
      loadInstances()
    }
  }
})

function handleCancel() {
  store.closeRelationshipEditor()
}

async function handleSave() {
  const hasSource = !!form.value.sourceId
  const hasTarget = !!form.value.targetId

  // 源/目标：要么都不填，要么都填；但若都不填，也不阻止保存（后端会校验）
  if (hasSource !== hasTarget) {
    message.warning('源节点和目标节点请同时填写或同时留空')
    return
  }
  if (hasSource && !hasTarget) {
    message.warning('请同时选择源节点和目标节点')
    return
  }
  if (!form.value.type.trim()) {
    message.warning('请选择或输入关系类型')
    return
  }

  saving.value = true
  try {
    const props: Record<string, unknown> = {}
    for (const p of properties.value) {
      if (p.key.trim()) {
        props[p.key.trim()] = p.value
      }
    }

    if (isEdit.value && store.editingRelationship) {
      await updateRelationshipFull(store.editingRelationship.element_id, {
        source_element_id: form.value.sourceId,
        target_element_id: form.value.targetId,
        type: form.value.type.trim(),
        properties: props,
      })
      message.success('关系更新成功')
    } else {
      await createRelationship({
        source_element_id: form.value.sourceId,
        target_element_id: form.value.targetId,
        type: form.value.type.trim(),
        properties: props,
      })
      message.success('关系创建成功')
    }

    store.triggerTreeRefresh()
    store.closeRelationshipEditor()
  } catch (err: any) {
    const detail = err?.response?.data?.detail || '操作失败'
    message.error(typeof detail === 'string' ? detail : '操作失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <a-modal
    v-model:open="visible"
    :title="title"
    :width="560"
    :confirm-loading="saving"
    :mask-closable="false"
    @cancel="handleCancel"
    @ok="handleSave"
    ok-text="保存"
    cancel-text="取消"
  >
    <a-form layout="vertical" :model="form">
      <!-- 源节点（下拉菜单支持本地搜索筛选） -->
      <a-form-item label="源节点 (Source)">
        <a-select
          v-model:value="form.sourceId"
          show-search
          allow-clear
          placeholder="搜索并选择源节点..."
          option-filter-prop="label"
          :filter-option="filterNodeOption"
          :options="allNodes"
          :loading="loadingNodes"
          not-found-content="暂无匹配节点"
          @select="handleSelectSource"
        />
      </a-form-item>

      <!-- 关系类型 -->
      <a-form-item label="关系类型 (Type)" required>
        <a-select
          v-model:value="form.type"
          placeholder="选择已有类型或输入新类型..."
          :options="relationshipTypeOptions"
          :loading="loadingTypes"
          :filter-option="(input: string, option: any) =>
            option.value.toLowerCase().includes(input.toLowerCase())
          "
          mode=""
          show-search
        />
      </a-form-item>

      <!-- 目标节点 + 交换按钮 -->
      <a-form-item label="目标节点 (Target)">
        <div style="display: flex; gap: 8px; align-items: center">
          <a-select
            v-model:value="form.targetId"
            show-search
            allow-clear
            placeholder="搜索并选择目标节点..."
            option-filter-prop="label"
            :filter-option="filterNodeOption"
            :options="allNodes"
            :loading="loadingNodes"
            not-found-content="暂无匹配节点"
            style="flex: 1"
            @select="handleSelectTarget"
          />
          <a-tooltip title="交换源/目标方向">
            <a-button @click="swapSourceTarget">
              <SwapOutlined />
            </a-button>
          </a-tooltip>
        </div>
      </a-form-item>

      <!-- 属性 -->
      <a-form-item label="属性">
        <div class="property-list">
          <div v-if="properties.length === 0" class="empty-hint">
            暂无属性，点击下方按钮添加
          </div>
          <div
            v-for="(prop, index) in properties"
            :key="index"
            class="property-row"
          >
            <a-input
              v-model:value="prop.key"
              placeholder="属性名"
              class="prop-key"
            />
            <span class="prop-sep">=</span>
            <a-input
              v-model:value="prop.value"
              placeholder="属性值"
              class="prop-value"
            />
            <a-button
              type="text"
              danger
              size="small"
              @click="removeProperty(index)"
            >
              <DeleteOutlined />
            </a-button>
          </div>
          <a-button type="dashed" block @click="addProperty" style="margin-top: 8px">
            <PlusOutlined /> 添加属性
          </a-button>
        </div>
      </a-form-item>
    </a-form>

    <!-- 编辑模式下显示该类型的所有关系实例 -->
    <div v-if="isEdit" class="instances-section">
      <div class="instances-title">
        当前「{{ store.editingRelationship?.type_label || store.editingRelationship?.type || '' }}」关系的实例列表
        <span class="instances-count">（共 {{ instances.length }} 条）</span>
      </div>
      <a-spin :spinning="loadingInstances">
        <div v-if="instances.length === 0 && !loadingInstances" class="instances-empty">
          暂无该类型的关系实例
        </div>
        <div v-else class="instances-list">
          <div
            v-for="inst in instances"
            :key="inst.element_id"
            class="instance-row"
          >
            <span class="instance-source" :title="inst.source_label + ': ' + inst.source_name">
              {{ inst.source_name }}
            </span>
            <span class="instance-arrow">→</span>
            <span class="instance-target" :title="inst.target_label + ': ' + inst.target_name">
              {{ inst.target_name }}
            </span>
          </div>
        </div>
      </a-spin>
    </div>
  </a-modal>
</template>

<style scoped>
.empty-hint {
  padding: 16px 0;
  text-align: center;
  color: #bbb;
  font-size: 12px;
}

.property-list {
  width: 100%;
}

.property-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.prop-key {
  width: 160px;
  flex-shrink: 0;
}

.prop-sep {
  color: #bbb;
  font-size: 14px;
  flex-shrink: 0;
}

.prop-value {
  flex: 1;
}

/* 关系实例列表 */
.instances-section {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.instances-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin-bottom: 10px;
}

.instances-count {
  font-weight: 400;
  color: #999;
  font-size: 12px;
}

.instances-empty {
  padding: 20px 0;
  text-align: center;
  color: #bbb;
  font-size: 12px;
}

.instances-list {
  max-height: 180px;
  overflow-y: auto;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  background: #fafafa;
}

.instance-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  font-size: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.instance-row:last-child {
  border-bottom: none;
}

.instance-source,
.instance-target {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #1677ff;
}

.instance-arrow {
  flex-shrink: 0;
  color: #bbb;
  font-size: 14px;
}
</style>
