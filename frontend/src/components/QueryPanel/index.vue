<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  SendOutlined,
  SearchOutlined,
  InfoCircleOutlined,
  NodeIndexOutlined,
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { useAppStore } from '@/stores'
import { fetchNodeDetail, postQuery } from '@/api'
import type { NodeDetail, QueryResponse } from '@/types'

const store = useAppStore()

const question = ref('')
const asking = ref(false)
const conversation = ref<Array<{ role: 'user' | 'ai'; content: string }>>([])

// 节点详情相关
const detail = ref<NodeDetail | null>(null)
const detailLoading = ref(false)
const detailError = ref('')
const isCategoryNode = ref(false) // 是否选中了分类节点（非实体）

// 监听选中节点，加载详情
watch(
  () => store.selectedNode,
  async (node) => {
    if (!node) {
      detail.value = null
      detailError.value = ''
      isCategoryNode.value = false
      return
    }

    // 关系元数据/根节点只展示摘要，不发请求
    if (node.type === '__RELATIONSHIP_ROOT__' || node.type === '__RELATIONSHIP__' || node.type === '__REL_META__') {
      detail.value = null
      detailError.value = ''
      isCategoryNode.value = true
      return
    }

    // 没有 elementId 的类型节点（如点击 "Disease" 分类）
    if (!node.elementId) {
      detail.value = null
      detailError.value = ''
      isCategoryNode.value = true
      return
    }

    isCategoryNode.value = false
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

  try {
    const res = await postQuery({ question: q })
    conversation.value.push({ role: 'ai', content: res.answer })
  } catch (e: any) {
    const errMsg = e?.response?.data?.detail || '查询失败，请检查后端服务'
    message.error(errMsg)
    conversation.value.pop()
  } finally {
    asking.value = false
  }
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
        <template v-else-if="detail">
          <div class="detail-node-name">{{ detail.name }}</div>
          <a-tag :color="detail.type === 'Disease' ? 'red' : 'blue'">{{ detail.type }}</a-tag>
          <a-divider style="margin: 12px 0" />

          <!-- 属性列表 -->
          <div v-if="detail.properties.length > 0" class="detail-props">
            <div class="sub-title">属性</div>
            <div v-for="prop in detail.properties" :key="prop.key" class="prop-row">
              <span class="prop-key">{{ prop.key }}</span>
              <span class="prop-value">{{ prop.value }}</span>
            </div>
          </div>

          <!-- 关系列表 -->
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
            :auto-size="{ minRows: 4, maxRows: 10 }"
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
        <div class="conversation-body">
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
  height: 40%;
  min-height: 300px;
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
}

.panel-header :deep(.anticon) {
  color: #1890ff;
  font-size: 14px;
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
  justify-content: center;
  align-items: center;
  overflow: hidden;
}

/* 输入区域 — 在查询区域中垂直居中 */
.input-area {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 16px;
  background: #fff;
  flex-shrink: 0;
  min-height: 200px;
  width: 100%;
}

.input-area :deep(textarea.ant-input) {
  resize: vertical;
  min-height: 180px !important;
  height: 100% !important;
  font-size: 14px;
  line-height: 1.6;
}

.input-area :deep(.ant-btn) {
  flex-shrink: 0;
}

/* 对话结果区域 — 有内容时自然展示在输入框下方 */
.conversation-body {
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
