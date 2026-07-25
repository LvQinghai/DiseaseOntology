<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? '编辑实体' : '新增实体'"
    width="560px"
    :confirm-loading="saving"
    @ok="handleSave"
    @cancel="handleCancel"
    :destroy-on-close="true"
  >
    <a-form layout="vertical" :model="form" ref="formRef">
      <!-- 标签选择（仅新建时显示） -->
      <a-form-item label="标签 (Label)" required v-if="!isEdit">
        <div style="display: flex; gap: 8px">
          <a-select
            v-model:value="form.label"
            style="flex: 1"
            placeholder="选择已有标签或输入新标签名..."
            :options="labelOptions"
            :loading="loadingLabels"
            :filter-option="false"
            @search="handleLabelSearch"
            mode=""
            show-search
          >
            <template #notFoundContent>
              <div style="padding: 4px 8px;">
                输入 "<span style="color: #1677ff">{{ labelSearchText }}</span>" 以创建新标签
              </div>
            </template>
          </a-select>
        </div>
      </a-form-item>

      <!-- 标签（编辑时只读显示） -->
      <a-form-item label="标签" v-if="isEdit">
        <a-input :value="form.label" disabled />
      </a-form-item>

      <!-- 名称 -->
      <a-form-item label="名称 (Name)" required>
        <a-input
          v-model:value="form.name"
          placeholder="输入实体名称..."
          :maxlength="200"
        />
      </a-form-item>

      <!-- 属性编辑 -->
      <a-form-item label="属性">
        <div class="property-list">
          <div v-if="properties.length === 0" class="empty-hint">
            暂无自定义属性，点击下方按钮添加
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
              :status="prop.keyError ? 'error' : ''"
              @blur="validatePropKey(index)"
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
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import {
  PlusOutlined,
  DeleteOutlined,
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import {
  createEntity,
  updateEntity,
  fetchAvailableLabels,
} from '@/api'
import { useAppStore } from '@/stores'

const store = useAppStore()

// 弹窗可见性
const visible = computed({
  get: () => store.entityEditorVisible,
  set: (v) => { if (!v) store.closeEntityEditor() },
})

const isEdit = computed(() => store.entityEditorMode === 'edit')

// 表单
const form = ref({ label: '', name: '' })
const properties = ref<Array<{ key: string; value: string; keyError?: boolean }>>([])
const saving = ref(false)

// 标签下拉
const availableLabels = ref<string[]>([])
const loadingLabels = ref(false)
const labelSearchText = ref('')

const labelOptions = computed(() => {
  const options = availableLabels.value.map((l) => ({ value: l, label: l }))
  // 如果有搜索文字且不匹配任何已有标签，添加"新建"选项
  if (labelSearchText.value && !availableLabels.value.includes(labelSearchText.value)) {
    options.unshift({
      value: labelSearchText.value,
      label: `新建 "${labelSearchText.value}"`,
    })
  }
  return options
})

async function loadLabels() {
  loadingLabels.value = true
  try {
    const res = await fetchAvailableLabels(store.currentSystemId)
    availableLabels.value = res.labels || []
  } catch {
    // 静默处理
  } finally {
    loadingLabels.value = false
  }
}

function handleLabelSearch(val: string) {
  labelSearchText.value = val
}

// 属性操作
function addProperty() {
  properties.value.push({ key: '', value: '' })
}

function removeProperty(index: number) {
  properties.value.splice(index, 1)
}

function validatePropKey(index: number) {
  const prop = properties.value[index]
  if (!prop.key.trim()) {
    prop.keyError = false
    return
  }
  // 检查重复
  const dup = properties.value.filter((p, i) => i !== index && p.key === prop.key)
  prop.keyError = dup.length > 0
}

// 初始化编辑数据
function initFromEntity() {
  if (isEdit.value && store.editingEntity) {
    const entity = store.editingEntity
    form.value.label = entity.labels?.[0] || ''
    form.value.name = entity.name || ''
    const props = entity.properties || {}
    properties.value = Object.entries(props)
      .filter(([k]) => k !== 'name')
      .map(([k, v]) => ({ key: k, value: String(v ?? '') }))
  } else {
    form.value.label = store.presetLabel || ''
    form.value.name = ''
    properties.value = []
  }
}

// 保存
async function handleSave() {
  if (!form.value.label.trim()) {
    message.warning('请选择或输入标签')
    return
  }
  if (!form.value.name.trim()) {
    message.warning('请输入实体名称')
    return
  }
  // 检查属性名重复
  const keys = properties.value.map((p) => p.key.trim()).filter(Boolean)
  if (new Set(keys).size !== keys.length) {
    message.warning('存在重复的属性名')
    return
  }

  saving.value = true
  try {
    const propsObj: Record<string, unknown> = {}
    properties.value.forEach((p) => {
      if (p.key.trim() && p.value.trim()) {
        propsObj[p.key.trim()] = p.value.trim()
      }
    })

    if (isEdit.value) {
      await updateEntity(store.editingElementId, {
        name: form.value.name.trim(),
        label: form.value.label.trim(),
        properties: propsObj,
      })
      message.success('实体更新成功')
    } else {
      await createEntity({
        label: form.value.label.trim(),
        name: form.value.name.trim(),
        properties: propsObj,
      })
      message.success('实体创建成功')
    }

    store.closeEntityEditor()
    store.triggerTreeRefresh()
    // 刷新详情（如果正在查看同一节点）
    if (isEdit.value && store.selectedNode) {
      // 触发重新加载详情
      store.selectNode(
        form.value.label.trim(),
        form.value.name.trim(),
        store.editingElementId,
      )
    }
  } catch (err: any) {
    const detail = err?.response?.data?.detail || '操作失败'
    message.error(typeof detail === 'string' ? detail : '操作失败，请检查输入')
  } finally {
    saving.value = false
  }
}

function handleCancel() {
  store.closeEntityEditor()
}

watch(visible, (val) => {
  if (val) {
    loadLabels()
    initFromEntity()
  }
})
</script>

<style scoped>
.property-list {
  max-height: 240px;
  overflow-y: auto;
}

.empty-hint {
  text-align: center;
  color: #bbb;
  padding: 16px 0;
  font-size: 13px;
}

.property-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.prop-key {
  flex: 1;
}

.prop-value {
  flex: 2;
}

.prop-sep {
  color: #999;
  font-weight: bold;
  font-size: 16px;
}
</style>
