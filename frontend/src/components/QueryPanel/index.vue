<script setup lang="ts">
import { ref, watch, nextTick, h } from 'vue'
import {
  SendOutlined,
  SearchOutlined,
  InfoCircleOutlined,
  NodeIndexOutlined,
  EditOutlined,
  DeleteOutlined,
} from '@ant-design/icons-vue'
import { message, Modal } from 'ant-design-vue'
import { useAppStore } from '@/stores'
import { fetchNodeDetail, postQuery, deleteEntity, checkEntityDeletion, fetchRelationship, deleteRelationship } from '@/api'
import type { NodeDetail, QueryResponse, RelationshipResponse, DeletionCheckResult } from '@/types'

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
      return
    }

    // 关系元数据/根节点只展示摘要
    if (node.type === '__RELATIONSHIP_ROOT__' || node.type === '__REL_META__') {
      detail.value = null
      relDetail.value = null
      detailError.value = ''
      isCategoryNode.value = true
      isRelationNode.value = false
      return
    }

    // 关系节点（左侧树中的关系类型：无具体 elementId → 分类摘要）
    if (node.type === '__RELATIONSHIP__') {
      if (!node.elementId) {
        detail.value = null
        relDetail.value = null
        detailError.value = ''
        isCategoryNode.value = true
        isRelationNode.value = false
        return
      }

      detail.value = null
      detailError.value = ''
      isCategoryNode.value = false
      isRelationNode.value = true
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
      return
    }

    // 实体节点
    isCategoryNode.value = false
    isRelationNode.value = false
    relDetail.value = null
    detailLoading.value = true
    detailError.value = ''
    try {
      detail.value = await fetchNodeDetail(node.elementId)
    } catch (e: any) {
      detailError.value = e?.response?.data?.detail || '加载节点详情失败'
      detail.value = null
    } finally {
      detailLoading.value = false
    }
  },
  { immediate: true },
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
    const res = await postQuery({ question: q })
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
    // 存在关联关系，弹窗展示详情并引导用户
    const relList = checkResult.relationships
    const relItems = relList.map(
      (r) => {
        const arrow = r.direction === 'outgoing' ? '→' : '←'
        const sourcePart = r.direction === 'outgoing' ? node.name : r.other_node_name
        const targetPart = r.direction === 'outgoing' ? r.other_node_name : node.name
        return `  • ${sourcePart} ${arrow}[${r.type}]${arrow} ${targetPart}`
      }
    ).join('\n')

    Modal.warning({
      title: `无法删除 "${node.name}"`,
      width: 560,
      content: h('div', null, [
        h('p', { style: { marginBottom: '12px', color: '#ff4d4f', fontWeight: 'bold' } },
          `该节点仍有 ${checkResult.relationship_count} 条关联关系，无法直接删除。`
        ),
        h('p', { style: { marginBottom: '8px' } }, '关联关系列表：'),
        h('pre', {
          style: {
            background: '#fafafa', padding: '8px 12px', borderRadius: '6px',
            fontSize: '13px', lineHeight: '1.8', maxHeight: '200px',
            overflowY: 'auto', marginBottom: '12px',
          },
        }, relItems),
        h('div', { style: { color: '#666', fontSize: '13px', lineHeight: '1.8' } }, [
          h('strong', null, '操作指引：'),
          h('br'),
          '1. 在左侧面板"关系"目录下找到上述关系类型',
          h('br'),
          '2. 点击对应关系进入详情，使用 ',
          h('span', { style: { background: '#fff1f0', color: '#ff4d4f', padding: '2px 6px', borderRadius: '3px' } }, '删除'),
          ' 按钮逐条删除',
          h('br'),
          '3. 或切换到图谱视图，选中关联边后删除',
          h('br'),
          '4. 所有关系删除完毕后，即可删除该实体',
        ]),
      ]),
      okText: '我知道了',
    })
    return
  }

  // 无关联关系，允许删除
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
      </div>
      <div class="detail-body">
        <template v-if="!store.selectedNode">
          <a-empty description="点击左侧本体树或图谱节点查看详情" :image-style="{ height: '40px' }" />
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

        <!-- v2.0: 关系详情展示 -->
        <template v-else-if="isRelationNode && relDetail">
          <div class="detail-rel-header">
            <span class="detail-rel-source">{{ relDetail.source_name }}</span>
            <span class="detail-rel-arrow">→</span>
            <a-tag color="blue">{{ relDetail.type }}</a-tag>
            <span class="detail-rel-arrow">→</span>
            <span class="detail-rel-target">{{ relDetail.target_name }}</span>
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
              :key="`${rel.type}-${rel.targetName}`"
              class="rel-row"
              @click="store.selectNode(rel.targetType, rel.targetName, rel.targetElementId || '')"
            >
              <span class="rel-type">{{ rel.type }}</span>
              <span class="rel-arrow">{{ rel.direction === 'out' ? '→' : '←' }}</span>
              <span class="rel-target">{{ rel.targetName }}</span>
            </div>
          </div>
        </template>
        <template v-else>
          <a-empty description="暂无数据" :image-style="{ height: '30px' }" />
        </template>
      </div>
    </div>

    <!-- 疾病与诊疗查询 -->
    <div class="panel-section query-section">
      <div class="panel-header">
        <SearchOutlined />
        <span>疾病与诊疗查询</span>
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

.rel-target {
  color: #262626;
  font-weight: 500;
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
</style>
