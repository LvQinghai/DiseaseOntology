<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  ApartmentOutlined,
  FolderOutlined,
  LinkOutlined,
  MinusSquareOutlined,
  PlusSquareOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  DownOutlined,
} from '@ant-design/icons-vue'
import { message, Modal } from 'ant-design-vue'
import { useAppStore } from '@/stores'
import { fetchOntologyTree, fetchSubclassChildren, deleteEntity } from '@/api'
import type { OntologyTreeNode } from '@/types'

const store = useAppStore()

const treeData = ref<OntologyTreeNode[]>([])
const loading = ref(false)
const selectedKeys = ref<string[]>([])
const expandedKeys = ref<string[]>([])
const treeVersion = ref(0)

// 右键菜单状态
const contextMenuVisible = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const contextNode = ref<TreeNode | null>(null)
const deleting = ref(false)

// ant-design-vue 需要的树节点类型
interface TreeNode {
  key: string
  title?: string
  children?: TreeNode[]
  isLeaf: boolean
  nodeType: string
  nodeName: string
  elementId: string
  label: string
  count: number
  slots?: { title: string }
}

/** 节点类型 → 颜色映射（与图谱统一） */
const typeColorMap: Record<string, string> = {
  Disease: '#f5222d',
  Symptom: '#fa8c16',
  Drug: '#1890ff',
  BodyPart: '#52c41a',
  SideEffect: '#722ed1',
}

/** 简便取色 */
function typeColor(nodeType: string): string {
  return typeColorMap[nodeType] || '#bfbfbf'
}

/** 从图谱数据中统计节点/关系类型数 */
const stats = computed(() => {
  const g = store.graphData
  if (!g) return { nodeTypeCount: 0, edgeTypeCount: 0, nodeCount: 0, edgeCount: 0 }
  const nodeTypes = new Set(g.nodes.map((n: any) => n.type).filter(Boolean))
  const edgeTypes = new Set(g.edges.map((e: any) => e.type || e.label).filter(Boolean))
  return {
    nodeTypeCount: nodeTypes.size,
    edgeTypeCount: edgeTypes.size,
    nodeCount: g.nodes.length,
    edgeCount: g.edges.length,
  }
})

function buildTreeData(nodes: OntologyTreeNode[]): TreeNode[] {
  return nodes.map((node) => {
    // 实体节点（有 elementId）：根据 childCount 判断是否为叶节点
    // 分类节点（无 elementId）：根据是否有 children 判断
    const isLeafNode = node.elementId
      ? (!node.childCount || node.childCount === 0)
      : (!node.children || node.children.length === 0)

    return {
      key: `${node.nodeType}::${node.name}`,
      label: node.label,
      count: node.count || 0,
      isLeaf: isLeafNode,
      nodeType: node.nodeType,
      nodeName: node.name,
      elementId: node.elementId || '',
      children: node.children ? buildTreeData(node.children) : (node.elementId ? [] : undefined),
      slots: { title: node.name },
    }
  })
}

// 关键修复：将 buildTreeData 的结果缓存到 ref 中，
// 避免每次组件重渲染都创建新对象导致 onLoadData 的修改丢失
const treeNodeData = ref<TreeNode[]>([])

watch(treeData, (newTreeData) => {
  treeNodeData.value = buildTreeData(newTreeData)
}, { deep: true, immediate: true })

/** 懒加载：展开实体节点时按需获取 SUB_CLASS_OF 子类 */
async function onLoadData(treeNode: any): Promise<void> {
  const dataRef = treeNode.dataRef
  if (!dataRef) return

  // 如果已有子节点（非空数组），说明已加载过，直接跳过
  if (dataRef.children && dataRef.children.length > 0) {
    return
  }

  const { elementId } = dataRef
  if (!elementId) return

  try {
    const children = await fetchSubclassChildren(elementId)
    if (children.length > 0) {
      const newChildren = children.map((c) => ({
        key: `${c.labels?.[0] || 'Unknown'}::${c.name}`,
        label: c.name,
        count: 0,
        isLeaf: !c.child_count || c.child_count === 0,
        nodeType: c.labels?.[0] || 'Unknown',
        nodeName: c.name,
        elementId: c.element_id,
        children: [],
        slots: { title: c.name },
      }))
      // 直接修改 dataRef，因为 treeNodeData 是稳定引用的 ref
      dataRef.children = newChildren
      dataRef.isLeaf = false
    } else {
      dataRef.isLeaf = true
    }
  } catch (e) {
    console.error('加载子类失败:', e)
    dataRef.isLeaf = true
  }
}

function handleSelect(_keys: any, info: any) {
  const { nodeType, nodeName, elementId } = info.node
  store.selectNode(nodeType, nodeName, elementId)
  selectedKeys.value = [info.node.key]
}

async function loadData() {
  loading.value = true
  try {
    const tree = await fetchOntologyTree()
    treeData.value = tree.roots
    expandedKeys.value = tree.roots.map((r) => `${r.nodeType}::${r.name}`)
    // 增量 key 强制 tree 组件完全重新挂载
    treeVersion.value++
  } catch (e) {
    console.error('加载本体树失败:', e)
  } finally {
    loading.value = false
  }
}

watch(
  () => store.selectedNode,
  (node) => {
    if (node) {
      selectedKeys.value = [`${node.type}::${node.name}`]
    }
  },
)

// v2.0: 监听树刷新信号
watch(
  () => store.treeRefreshKey,
  () => { loadData() },
)

// ---- 右键菜单 ----

function findTreeNodeByKey(key: string, nodes: TreeNode[]): TreeNode | null {
  for (const node of nodes) {
    if (node.key === key) return node
    if (node.children) {
      const found = findTreeNodeByKey(key, node.children)
      if (found) return found
    }
  }
  return null
}

function handleTreeRightClick({ event, node }: any) {
  const treeNode = findTreeNodeByKey(node.key, treeNodeData.value)
  if (!treeNode || !treeNode.elementId) {
    // 非实体节点不显示右键菜单
    return
  }
  event.preventDefault()
  contextNode.value = treeNode
  contextMenuX.value = event.clientX
  contextMenuY.value = event.clientY
  contextMenuVisible.value = true
}

function closeContextMenu() {
  contextMenuVisible.value = false
  contextNode.value = null
}

function handleContextEdit() {
  if (!contextNode.value) return
  const entity = {
    element_id: contextNode.value.elementId,
    labels: [contextNode.value.nodeType],
    name: contextNode.value.nodeName,
    properties: {},
    relationship_count: 0,
  }
  store.openEntityEditor('edit', entity)
  closeContextMenu()
}

function handleContextAddSubclass() {
  if (!contextNode.value) return
  store.openCreateEntityWithLabel(contextNode.value.nodeType)
  closeContextMenu()
}

function handleContextAddRelation() {
  if (!contextNode.value) return
  store.openRelationshipEditor(
    contextNode.value.elementId,
    contextNode.value.nodeName,
  )
  closeContextMenu()
}

async function handleContextDelete() {
  if (!contextNode.value) return
  const node = contextNode.value
  closeContextMenu()

  Modal.confirm({
    title: `删除 "${node.nodeName}"`,
    content: `确定要删除实体"${node.nodeName}"吗？此操作不可撤销，与该实体关联的所有关系也将被删除。`,
    okText: '确认删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      deleting.value = true
      try {
        await deleteEntity(node.elementId)
        message.success('删除成功')
        store.triggerTreeRefresh()
        if (store.selectedNode?.elementId === node.elementId) {
          store.clearSelection()
        }
      } catch (err: any) {
        const detail = err?.response?.data?.detail || '删除失败'
        message.error(typeof detail === 'string' ? detail : '删除失败')
      } finally {
        deleting.value = false
      }
    },
  })
}

// 点击外部关闭右键菜单
function handleDocumentClick() {
  contextMenuVisible.value = false
}

// v2.0: 头部新增下拉菜单
function handleAddMenuClick({ key }: { key: string }) {
  if (key === 'entity') {
    store.openEntityEditor('create')
  } else if (key === 'relationship') {
    store.openRelationshipEditor('', '')
  }
}

onMounted(() => {
  loadData()
  document.addEventListener('click', handleDocumentClick)
})

defineExpose({ loadData })
</script>

<template>
  <div class="ontology-browser">
    <div class="panel-header">
      <ApartmentOutlined />
      <span>本体与关系浏览器</span>
      <a-dropdown :trigger="['click']">
        <a-button type="default" size="small" class="header-add-btn">
          <PlusOutlined /> 新增 <DownOutlined style="font-size:10px" />
        </a-button>
        <template #overlay>
          <a-menu @click="handleAddMenuClick">
            <a-menu-item key="entity">
              <ApartmentOutlined /> 新增实体
            </a-menu-item>
            <a-menu-item key="relationship">
              <LinkOutlined /> 新增关系
            </a-menu-item>
          </a-menu>
        </template>
      </a-dropdown>
    </div>

    <!-- 快速统计条 -->
    <div v-if="!loading && stats.nodeCount > 0" class="stats-bar">
      <span class="stats-item">
        <i class="stats-dot" style="background:#1890ff"></i>{{ stats.nodeCount }} 个节点
      </span>
      <span class="stats-item">
        <i class="stats-dot" style="background:#52c41a"></i>{{ stats.edgeCount }} 条关系
      </span>
    </div>

    <a-spin :spinning="loading" wrapper-class-name="tree-spin">
      <a-tree
        v-if="treeNodeData.length > 0"
        :key="treeVersion"
        :tree-data="treeNodeData"
        :selected-keys="selectedKeys"
        :expanded-keys="expandedKeys"
        :load-data="onLoadData"
        show-line
        block-node
        @select="handleSelect"
        @expand="(keys: string[]) => (expandedKeys = keys)"
        @rightClick="handleTreeRightClick"
      >
        <!-- 自定义节点渲染 -->
        <template #title="{ label, nodeType, count, elementId, nodeName }">
          <!-- 关系根节点 -->
          <span v-if="nodeType === '__RELATIONSHIP_ROOT__'" class="tree-node tree-node-root">
            <LinkOutlined class="node-icon-root" />
            <span class="node-label-root">{{ label }}</span>
            <span v-if="count > 0" class="node-count-root">{{ count }}</span>
          </span>

          <!-- 关系子节点 -->
          <span v-else-if="nodeType === '__RELATIONSHIP__'" class="tree-node tree-node-rel">
            <span class="node-label-rel">{{ nodeName }}</span>
          </span>

          <!-- 实体分类根节点（非关系、无 elementId） -->
          <span v-else-if="!elementId" class="tree-node tree-node-category">
            <FolderOutlined class="node-icon-category" />
            <span class="node-label-category">{{ label }}</span>
            <span v-if="count > 0" class="node-count-badge">{{ count }}</span>
          </span>

          <!-- 实体节点（有 elementId） -->
          <span v-else class="tree-node tree-node-entity">
            <span class="node-type-dot" :style="{ background: typeColor(nodeType) }"></span>
            <span class="node-label-entity">{{ label || nodeName }}</span>
            <span class="node-type-tag" :style="{ color: typeColor(nodeType), borderColor: typeColor(nodeType) }">
              {{ nodeType }}
            </span>
          </span>
        </template>

        <!-- 展开/折叠图标 -->
        <template #switcherIcon="{ expanded, selected }">
          <MinusSquareOutlined v-if="expanded" class="tree-switcher tree-switcher-open" />
          <PlusSquareOutlined v-else class="tree-switcher tree-switcher-closed" />
        </template>
      </a-tree>

      <a-empty v-else-if="!loading" description="暂无本体数据" />
    </a-spin>

    <!-- v2.0: 右键上下文菜单 -->
    <Teleport to="body">
      <div
        v-if="contextMenuVisible && contextNode"
        class="context-menu-overlay"
        :style="{ left: contextMenuX + 'px', top: contextMenuY + 'px' }"
        @click.stop
      >
        <div class="context-menu">
          <div class="context-menu-item" @click="handleContextEdit">
            <EditOutlined /> 编辑节点
          </div>
          <div class="context-menu-item" @click="handleContextAddSubclass">
            <PlusOutlined /> 新增子类
          </div>
          <div class="context-menu-item" @click="handleContextAddRelation">
            <LinkOutlined /> 新增关系
          </div>
          <div class="context-menu-divider" />
          <div
            class="context-menu-item context-menu-danger"
            @click="handleContextDelete"
          >
            <DeleteOutlined /> 删除节点
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.ontology-browser {
  height: 100%;
  display: flex;
  flex-direction: column;
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
}

.panel-header :deep(.anticon) {
  color: #1890ff;
  font-size: 14px;
}

/* ========== 统计条 ========== */
.stats-bar {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 8px 16px;
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.stats-item {
  font-size: 12px;
  color: #595959;
  display: flex;
  align-items: center;
  gap: 5px;
}

.stats-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

/* ========== 树容器 ========== */
.tree-spin {
  flex: 1;
  overflow-y: auto;
  padding: 6px 0 12px 4px;
}

:deep(.ant-tree) {
  background: transparent;
  color: #262626;
}

/* ========== 全局树节点 ========== */
:deep(.ant-tree-treenode) {
  padding: 0;
  transition: background 0.15s;
}

:deep(.ant-tree-node-content-wrapper) {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  margin: 1px 0;
  border-radius: 4px;
  transition: all 0.15s ease;
  line-height: 1.6;
  min-height: 28px;
}

:deep(.ant-tree-node-content-wrapper:hover) {
  background: #f0f5ff;
}

:deep(.ant-tree-node-selected) {
  background: #e6f7ff !important;
}

:deep(.ant-tree-node-selected .node-label-entity) {
  color: #1890ff;
}

/* ========== 连接线 ========== */
:deep(.ant-tree-show-line .ant-tree-indent-unit::before) {
  border-right-color: #e8e8e8;
}

:deep(.ant-tree-show-line .ant-tree-switcher) {
  background: transparent;
}

/* ========== 展开/折叠图标 ========== */
.tree-switcher {
  font-size: 14px;
  vertical-align: middle;
}

.tree-switcher-open {
  color: #1890ff;
}

.tree-switcher-closed {
  color: #bfbfbf;
  transition: color 0.15s;
}

:deep(.ant-tree-switcher:hover .tree-switcher-closed) {
  color: #1890ff;
}

/* ========== 叶子占位（虚线） ========== */
:deep(.ant-tree-switcher-noop) {
  color: #d9d9d9;
}

/* ========== 通用节点容器 ========== */
.tree-node {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
}

/* ========== 关系根节点 ========== */
.tree-node-root {
  gap: 6px;
}

.node-icon-root {
  color: #1890ff;
  font-size: 13px;
  flex-shrink: 0;
}

.node-label-root {
  font-size: 13px;
  font-weight: 600;
  color: #262626;
}

.node-count-root {
  font-size: 11px;
  font-weight: 500;
  color: #1890ff;
  background: #e6f7ff;
  padding: 0 5px;
  border-radius: 8px;
  line-height: 17px;
  min-width: 16px;
  text-align: center;
}

/* ========== 关系子节点 ========== */
.node-label-rel {
  font-size: 12px;
  color: #595959;
  font-style: italic;
}

/* ========== 分类节点 ========== */
.tree-node-category {
  gap: 6px;
}

.node-icon-category {
  color: #8c8c8c;
  font-size: 13px;
  flex-shrink: 0;
}

.node-label-category {
  font-size: 13px;
  font-weight: 500;
  color: #434343;
}

.node-count-badge {
  font-size: 11px;
  font-weight: 500;
  color: #595959;
  background: #f0f0f0;
  padding: 0 5px;
  border-radius: 8px;
  line-height: 17px;
  min-width: 16px;
  text-align: center;
}

/* ========== 实体节点 ========== */
.tree-node-entity {
  gap: 6px;
}

.node-type-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.06);
}

.node-label-entity {
  font-size: 13px;
  color: #262626;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-type-tag {
  font-size: 10px;
  font-weight: 500;
  border: 1px solid;
  border-radius: 3px;
  padding: 0 4px;
  line-height: 16px;
  flex-shrink: 0;
  opacity: 0.75;
}

/* ========== 加载动画 ========== */
:deep(.ant-tree-switcher-loading-icon) {
  color: #1890ff;
}

/* ========== v2.0 头部新增按钮 ========== */
.header-add-btn {
  margin-left: auto;
  height: 26px;
  padding: 0 10px;
  font-size: 12px;
  color: #1677ff;
  border-color: #1677ff;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.header-add-btn:hover {
  color: #fff !important;
  background: #1677ff !important;
  border-color: #1677ff !important;
}

.header-add-btn :deep(.anticon) {
  font-size: 10px;
  line-height: 1;
}

/* ========== v2.0 右键上下文菜单 ========== */
.context-menu-overlay {
  position: fixed;
  z-index: 9999;
}
.context-menu {
  min-width: 160px;
  background: #fff;
  border-radius: 6px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12), 0 3px 6px rgba(0, 0, 0, 0.08);
  padding: 4px;
}
.context-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  font-size: 13px;
  color: #262626;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.15s;
  user-select: none;
}
.context-menu-item:hover {
  background: #f0f5ff;
  color: #1890ff;
}
.context-menu-divider {
  height: 1px;
  background: #f0f0f0;
  margin: 4px 0;
}
.context-menu-danger:hover {
  background: #fff1f0;
  color: #ff4d4f;
}
</style>
