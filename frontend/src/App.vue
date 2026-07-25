<template>
  <div class="app-layout">
    <!-- ==================== Header ==================== -->
    <header class="app-header">
      <div class="header-left">
        <span class="app-logo">●</span>
        <!-- v3.0 系统切换下拉 -->
        <a-select
          v-model:value="store.currentSystemId"
          class="system-switcher"
          @change="onSystemChange"
          @dropdownVisibleChange="onSystemDropdownVisible"
        >
          <a-select-option
            v-for="sys in store.systemList"
            :key="sys.system_id"
            :value="sys.system_id"
          >
            {{ sys.name }}
          </a-select-option>
        </a-select>
      </div>
      <div class="header-right">
        <span class="header-subtitle">基于知识图谱的可视化系统</span>
        <div class="header-actions">
          <a-dropdown>
            <a-button type="primary" size="small" shape="round">
              <template #icon><ImportOutlined /></template>
              导入新数据
            </a-button>
            <template #overlay>
              <a-menu @click="onImportMenuClick">
                <a-menu-item key="excel">
                  <FileExcelOutlined /> 从 Excel 导入
                </a-menu-item>
                <a-menu-item key="database">
                  <DatabaseOutlined /> 从数据库导入
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>

          <a-button size="small" shape="round" @click="onDownloadTemplate">
            <template #icon><FileTextOutlined /></template>
            模板导出
          </a-button>

          <a-button type="text" size="small" @click="store.openSystemManager()" class="header-btn-text">
            <SettingOutlined /> 管理
          </a-button>
        </div>
      </div>
    </header>

    <!-- ==================== Body：v2.0 三面板布局 ==================== -->
    <div class="main-content">
      <!-- 左侧：本体浏览器 -->
      <aside class="panel-left" :style="leftPanelStyle">
        <OntologyBrowser v-if="!store.leftCollapsed" />
      </aside>

      <!-- 左分隔条（拖拽 + 折叠） -->
      <div class="panel-divider" @mousedown="startResize('left', $event)">
        <span class="divider-collapse-btn" @mousedown.stop @click="store.toggleLeft()">
          <MenuFoldOutlined v-if="!store.leftCollapsed" />
          <MenuUnfoldOutlined v-else />
        </span>
      </div>

      <!-- 中间：详情 + 智能问答 -->
      <main class="panel-center" :style="centerPanelStyle">
        <QueryPanel />
      </main>

      <!-- 右分隔条（拖拽 + 折叠） -->
      <div class="panel-divider" @mousedown="startResize('center', $event)">
        <span class="divider-collapse-btn" @mousedown.stop @click="store.toggleRight()">
          <MenuFoldOutlined v-if="!store.rightCollapsed" />
          <MenuUnfoldOutlined v-else />
        </span>
      </div>

      <!-- 右侧：图谱画布 -->
      <aside class="panel-right" :style="rightPanelStyle">
        <GraphCanvas v-if="!store.rightCollapsed" />
      </aside>
    </div>

    <!-- ==================== v2.0 编辑弹窗 ==================== -->
    <EntityEditor />
    <RelationshipEditor />

    <!-- ==================== v3.0 导入向导弹窗 ==================== -->
    <a-modal
      v-model:open="store.importWizardVisible"
      :title="importWizardTitle"
      width="700px"
      :footer="null"
      :maskClosable="false"
    >
      <div class="import-wizard">
        <!-- Step 1: Excel 上传 -->
        <div v-if="importStep === 0 && store.importSource === 'excel'" class="import-step">
          <a-upload-dragger
            :before-upload="handleExcelUpload"
            :show-upload-list="false"
            accept=".xlsx,.xls"
          >
            <p class="ant-upload-drag-icon"><InboxOutlined style="font-size:48px;color:#1677ff" /></p>
            <p class="ant-upload-text">点击或拖拽 Excel 文件到此处</p>
            <p class="ant-upload-hint">支持 .xlsx / .xls 格式</p>
          </a-upload-dragger>
          <div v-if="excelPreview" class="import-preview">
            <a-alert
              :message="`预览: ${excelPreview.total_entities} 个实体, ${excelPreview.total_relationships} 条关系`"
              type="success"
              show-icon
              style="margin-top:16px"
            />
            <div style="margin-top:16px">
              <a-button type="primary" @click="importStep = 1">下一步：配置系统名称</a-button>
            </div>
          </div>
          <div v-if="excelError" style="margin-top:12px">
            <a-alert :message="excelError" type="error" show-icon />
          </div>
        </div>

        <!-- Step 1: 数据库连接配置 -->
        <div v-if="importStep === 0 && store.importSource === 'database'" class="import-step">
          <a-form layout="vertical">
            <a-form-item label="数据库类型">
              <a-select v-model:value="dbConn.db_type" placeholder="选择数据库类型">
                <a-select-option value="mysql">MySQL</a-select-option>
                <a-select-option value="postgresql">PostgreSQL</a-select-option>
                <a-select-option value="mssql">SQL Server</a-select-option>
                <a-select-option value="sqlite">SQLite</a-select-option>
              </a-select>
            </a-form-item>
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="主机">
                  <a-input v-model:value="dbConn.host" placeholder="localhost" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="端口">
                  <a-input-number v-model:value="dbConn.port" :min="1" :max="65535" style="width:100%" />
                </a-form-item>
              </a-col>
            </a-row>
            <a-form-item label="数据库名">
              <a-input v-model:value="dbConn.database" placeholder="mydb" />
            </a-form-item>
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="用户名">
                  <a-input v-model:value="dbConn.user" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="密码">
                  <a-input-password v-model:value="dbConn.password" />
                </a-form-item>
              </a-col>
            </a-row>
          </a-form>
          <a-button
            type="primary"
            :loading="dbConnecting"
            @click="onTestConnection"
          >
            测试连接并获取表结构
          </a-button>
          <div v-if="dbConError" style="margin-top:12px">
            <a-alert :message="dbConError" type="error" show-icon />
          </div>
        </div>

        <!-- Step 2: 数据库表映射 -->
        <div v-if="importStep === 1 && store.importSource === 'database'" class="import-step">
          <h4>实体映射配置</h4>
          <div v-for="(mapping, idx) in entityMappings" :key="'em-'+idx" class="mapping-row">
            <a-select v-model:value="mapping.source_table" placeholder="源表" style="width:150px">
              <a-select-option v-for="t in dbTables" :key="t.name" :value="t.name">{{ t.name }}</a-select-option>
            </a-select>
            <a-select v-model:value="mapping.source_column" placeholder="来源列" style="width:150px;margin-left:8px">
              <a-select-option
                v-for="c in getColumnsForTable(mapping.source_table)"
                :key="c.name" :value="c.name"
              >{{ c.name }}</a-select-option>
            </a-select>
            <a-input v-model:value="mapping.target_label" placeholder="目标标签 (label)" style="width:150px;margin-left:8px" />
            <a-button type="text" danger @click="entityMappings.splice(idx,1)">删除</a-button>
          </div>
          <a-button type="dashed" @click="entityMappings.push({source_table:'',source_column:'',target_label:''})">
            + 添加实体映射
          </a-button>

          <h4 style="margin-top:20px">关系映射配置（可选）</h4>
          <div v-for="(mapping, idx) in relationshipMappings" :key="'rm-'+idx" class="mapping-row">
            <a-select v-model:value="mapping.source_table" placeholder="源表" style="width:130px">
              <a-select-option v-for="t in dbTables" :key="t.name" :value="t.name">{{ t.name }}</a-select-option>
            </a-select>
            <a-select v-model:value="mapping.source_column" placeholder="源列" style="width:130px;margin-left:8px">
              <a-select-option v-for="c in getColumnsForTable(mapping.source_table)" :key="c.name" :value="c.name">{{ c.name }}</a-select-option>
            </a-select>
            <a-input v-model:value="mapping.relationship_type" placeholder="关系类型" style="width:130px;margin-left:8px" />
            <a-select v-model:value="mapping.target_table" placeholder="目标表" style="width:130px;margin-left:8px">
              <a-select-option v-for="t in dbTables" :key="t.name" :value="t.name">{{ t.name }}</a-select-option>
            </a-select>
            <a-select v-model:value="mapping.target_column" placeholder="目标列" style="width:130px;margin-left:8px">
              <a-select-option v-for="c in getColumnsForTable(mapping.target_table)" :key="c.name" :value="c.name">{{ c.name }}</a-select-option>
            </a-select>
            <a-button type="text" danger @click="relationshipMappings.splice(idx,1)">删除</a-button>
          </div>
          <a-button type="dashed" @click="relationshipMappings.push({source_table:'',source_column:'',relationship_type:'',target_table:'',target_column:''})">
            + 添加关系映射
          </a-button>

          <div style="margin-top:20px">
            <a-button @click="importStep = 0">上一步</a-button>
            <a-button type="primary" style="margin-left:8px" :loading="dbPreviewing" @click="onPreviewDB">
              预览数据
            </a-button>
          </div>
        </div>

        <!-- Step 2 (Excel) / Step 3 (DB): 预览 + 系统名称 -->
        <div v-if="
          (importStep === 1 && store.importSource === 'excel') ||
          (importStep === 2 && store.importSource === 'database')
        " class="import-step">
          <h4>预览数据</h4>
          <a-alert
            :message="`共 ${previewTotalE} 个实体, ${previewTotalR} 条关系`"
            type="info"
            show-icon
          />
          <div v-if="previewSampleE.length > 0" style="margin-top:12px">
            <strong>实体样例（前 5 条）：</strong>
            <a-table
              :data-source="previewSampleE"
              :columns="previewEntityColumns"
              size="small"
              :pagination="false"
              style="margin-top:8px"
            />
          </div>
          <h4 style="margin-top:24px">系统信息</h4>
          <a-form layout="vertical">
            <a-form-item label="系统名称" required>
              <a-input v-model:value="newSystemName" placeholder="例如：汽车零件本体知识图谱" />
            </a-form-item>
            <a-form-item label="系统描述">
              <a-textarea v-model:value="newSystemDesc" placeholder="可选描述" :rows="2" />
            </a-form-item>
          </a-form>
          <div style="margin-top:16px">
            <a-button @click="importStep = (store.importSource === 'database' ? 1 : 0)">上一步</a-button>
            <a-button
              type="primary"
              style="margin-left:8px"
              :loading="importing"
              @click="onConfirmImport"
            >
              确认导入
            </a-button>
          </div>
          <div v-if="importResult" style="margin-top:16px">
            <a-alert
              v-if="importResult.success"
              :message="importResult.message"
              type="success"
              show-icon
            />
            <a-alert v-else :message="importResult.errors?.join(', ') || '导入失败'" type="error" show-icon />
          </div>
        </div>
      </div>
    </a-modal>

    <!-- ==================== v3.0 系统管理弹窗 ==================== -->
    <a-modal
      v-model:open="store.systemManagerVisible"
      title="系统管理"
      width="600px"
      :footer="null"
    >
      <a-table
        :data-source="store.systemList"
        :columns="systemColumns"
        :pagination="false"
        size="small"
        row-key="system_id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'prefix'">
            <a-tag color="blue">{{ record.prefix }}</a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-popconfirm
              title="确认删除该系统及其所有数据？"
              ok-text="确认删除"
              cancel-text="取消"
              @confirm="onDeleteSystem(record.system_id)"
              :disabled="record.system_id === 'disease_ontology'"
            >
              <a-button
                type="link"
                danger
                size="small"
                :disabled="record.system_id === 'disease_ontology'"
              >
                删除
              </a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons-vue'
import {
  InboxOutlined,
  ImportOutlined,
  FileExcelOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  SettingOutlined,
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { useAppStore } from '@/stores'
import OntologyBrowser from '@/components/OntologyBrowser/index.vue'
import GraphCanvas from '@/components/GraphCanvas/index.vue'
import QueryPanel from '@/components/QueryPanel/index.vue'
import EntityEditor from '@/components/EntityEditor/index.vue'
import RelationshipEditor from '@/components/RelationshipEditor/index.vue'
import {
  fetchSystemList,
  deleteSystem,
  previewExcel,
  importFromExcel,
  testDBConnection,
  getDBTables,
  previewDBImport,
  importFromDB,
  downloadTemplate,
} from '@/api'
import type {
  DBConnection,
  DBTableInfo,
  TableMapping,
  RelationshipMapping,
  ImportPreviewData,
  ImportResult,
} from '@/types'

const store = useAppStore()

// ==================== v2.0 面板拖拽 ====================
const leftWidth = ref(260)
const centerWidth = ref(380)
const MIN_WIDTH = 200
const MAX_LEFT = 500
const MAX_CENTER = 700

interface DragState {
  target: 'left' | 'center'
  startX: number
  startWidth: number
}

const dragging = ref<DragState | null>(null)

function startResize(target: 'left' | 'center', e: MouseEvent) {
  e.preventDefault()
  if (target === 'left' && store.leftCollapsed) {
    store.toggleLeft()
  }
  const currentWidth = target === 'left' ? leftWidth.value : centerWidth.value
  dragging.value = { target, startX: e.clientX, startWidth: currentWidth }
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function onMouseMove(e: MouseEvent) {
  if (!dragging.value) return
  const { target, startX, startWidth } = dragging.value
  const delta = e.clientX - startX
  const maxW = target === 'left' ? MAX_LEFT : MAX_CENTER
  const newWidth = Math.min(maxW, Math.max(MIN_WIDTH, startWidth + delta))
  if (target === 'left') {
    leftWidth.value = newWidth
  } else {
    centerWidth.value = newWidth
  }
}

function onMouseUp() {
  if (!dragging.value) return
  dragging.value = null
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

onMounted(() => {
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
})

onUnmounted(() => {
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
})

const leftPanelStyle = computed(() => ({
  width: store.leftCollapsed ? '0px' : leftWidth.value + 'px',
  minWidth: store.leftCollapsed ? '0px' : leftWidth.value + 'px',
}))

const centerPanelStyle = computed(() => ({
  width: centerWidth.value + 'px',
  minWidth: centerWidth.value + 'px',
}))

const rightPanelStyle = computed(() => {
  if (store.rightCollapsed) {
    return { flex: '0 0 0px', width: '0px', minWidth: '0px', borderLeft: 'none', overflow: 'hidden' }
  }
  return { flex: '1 1 0%' }
})

// ==================== v3.0 系统管理 ====================

const systemColumns = [
  { title: '系统名称', dataIndex: 'name', key: 'name' },
  { title: 'ID', dataIndex: 'system_id', key: 'system_id' },
  { title: '前缀', dataIndex: 'prefix', key: 'prefix' },
  { title: '实体数', dataIndex: 'node_count', key: 'node_count' },
  { title: '关系数', dataIndex: 'relationship_count', key: 'relationship_count' },
  { title: '来源', dataIndex: 'import_source', key: 'import_source' },
  { title: '操作', key: 'action' },
]

onMounted(async () => {
  try {
    const list = await fetchSystemList()
    if (list.length > 0) {
      store.setSystemList(list)
      // 默认选中第一个系统
      if (!store.currentSystemInfo) {
        store.setCurrentSystem(list[0].system_id)
      }
    }
  } catch (e) {
    console.error('加载系统列表失败:', e)
    // 兜底：确保有默认系统可选
    if (!store.currentSystemInfo) {
      store.setCurrentSystem('disease_ontology')
    }
  }
})

function onSystemChange(systemId: string) {
  store.setCurrentSystem(systemId)
  store.triggerTreeRefresh()
}

function onSystemDropdownVisible(visible: boolean) {
  if (visible) refreshSystemList()
}

async function refreshSystemList() {
  try {
    const list = await fetchSystemList()
    store.setSystemList(list)
  } catch { /* ignore */ }
}

async function onDeleteSystem(systemId: string) {
  try {
    await deleteSystem(systemId)
    store.removeSystem(systemId)
    message.success('系统已删除')
    store.triggerTreeRefresh()
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '删除失败')
  }
}

// ==================== v3.0 导入向导 ====================

const importStep = ref(0)
const importing = ref(false)
const importResult = ref<ImportResult | null>(null)

const excelFile = ref<File | null>(null)
const excelPreview = ref<ImportPreviewData | null>(null)
const excelError = ref('')

const dbConn = ref<DBConnection>({
  db_type: 'mysql',
  host: 'localhost',
  port: 3306,
  database: '',
  user: 'root',
  password: '',
})
const dbConnecting = ref(false)
const dbConError = ref('')
const dbTables = ref<DBTableInfo[]>([])
const dbPreviewing = ref(false)

const entityMappings = ref<TableMapping[]>([{ source_table: '', source_column: '', target_label: '' }])
const relationshipMappings = ref<RelationshipMapping[]>([])

const dbPreview = ref<ImportPreviewData | null>(null)

const newSystemName = ref('')
const newSystemDesc = ref('')

const importWizardTitle = computed(() => {
  if (store.importSource === 'excel') return '从 Excel 导入数据'
  return '从数据库导入数据'
})

const previewTotalE = computed(() => {
  if (store.importSource === 'excel') return excelPreview.value?.total_entities || 0
  return dbPreview.value?.total_entities || 0
})

const previewTotalR = computed(() => {
  if (store.importSource === 'excel') return excelPreview.value?.total_relationships || 0
  return dbPreview.value?.total_relationships || 0
})

const previewSampleE = computed(() => {
  const src = store.importSource === 'excel' ? excelPreview.value : dbPreview.value
  return src?.entities?.slice(0, 5) || []
})

const previewEntityColumns = computed(() => {
  if (previewSampleE.value.length === 0) return []
  return Object.keys(previewSampleE.value[0]).map(k => ({ title: k, dataIndex: k, key: k }))
})

function getColumnsForTable(tableName: string) {
  const t = dbTables.value.find(t => t.name === tableName)
  return t?.columns || []
}

function onImportMenuClick({ key }: { key: string }) {
  if (key === 'excel' || key === 'database') {
    resetImportState()
    store.openImportWizard(key as 'excel' | 'database')
  }
}

function resetImportState() {
  importStep.value = 0
  importing.value = false
  importResult.value = null
  excelFile.value = null
  excelPreview.value = null
  excelError.value = ''
  dbConn.value = { db_type: 'mysql', host: 'localhost', port: 3306, database: '', user: 'root', password: '' }
  dbConnecting.value = false
  dbConError.value = ''
  dbTables.value = []
  dbPreviewing.value = false
  dbPreview.value = null
  entityMappings.value = [{ source_table: '', source_column: '', target_label: '' }]
  relationshipMappings.value = []
  newSystemName.value = ''
  newSystemDesc.value = ''
}

async function handleExcelUpload(file: File) {
  excelFile.value = file
  excelError.value = ''
  try {
    excelPreview.value = await previewExcel(file)
  } catch (e: any) {
    excelError.value = e?.response?.data?.detail || '解析 Excel 失败'
    return false
  }
  return false
}

async function onTestConnection() {
  dbConError.value = ''
  dbConnecting.value = true
  try {
    const result = await testDBConnection(dbConn.value)
    if (!result.success) {
      dbConError.value = result.message
      return
    }
    dbTables.value = await getDBTables(dbConn.value)
    importStep.value = 1
  } catch (e: any) {
    dbConError.value = e?.response?.data?.detail || '连接或获取表结构失败'
  } finally {
    dbConnecting.value = false
  }
}

async function onPreviewDB() {
  dbPreviewing.value = true
  try {
    dbPreview.value = await previewDBImport(
      dbConn.value,
      entityMappings.value.filter(m => m.source_table),
      relationshipMappings.value.filter(m => m.source_table) || undefined,
    )
    importStep.value = 2
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '预览失败')
  } finally {
    dbPreviewing.value = false
  }
}

async function onConfirmImport() {
  if (!newSystemName.value.trim()) {
    message.warning('请输入系统名称')
    return
  }
  importing.value = true
  importResult.value = null
  try {
    if (store.importSource === 'excel' && excelFile.value) {
      importResult.value = await importFromExcel(
        excelFile.value,
        newSystemName.value.trim(),
        newSystemDesc.value.trim(),
      )
    } else {
      importResult.value = await importFromDB(
        dbConn.value,
        entityMappings.value.filter(m => m.source_table),
        newSystemName.value.trim(),
        newSystemDesc.value.trim(),
        relationshipMappings.value.filter(m => m.source_table) || undefined,
      )
    }
    if (importResult.value.success) {
      message.success('导入成功！')
      await refreshSystemList()
      store.setCurrentSystem(importResult.value.system_id)
      store.triggerTreeRefresh()
    }
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}

async function onDownloadTemplate() {
  try {
    const blob = await downloadTemplate()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'import_template.xlsx'
    a.click()
    URL.revokeObjectURL(url)
    message.success('模板下载成功')
  } catch {
    message.error('模板下载失败')
  }
}
</script>

<style>
/* ── 全局重置 ── */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: #f0f2f5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.app-layout {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* ── Header：v2.0 深蓝底色 + v3.0 系统切换/按钮 ── */
.app-header {
  height: 48px;
  background: linear-gradient(135deg, #001529 0%, #002140 50%, #001f33 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
  z-index: 100;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.06);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.app-logo {
  color: #1890ff;
  font-size: 16px;
  filter: drop-shadow(0 0 6px rgba(24, 144, 255, 0.4));
}

.system-switcher {
  min-width: 240px;
}

.system-switcher .ant-select-selector {
  background: rgba(255, 255, 255, 0.1) !important;
  border-color: rgba(255, 255, 255, 0.2) !important;
  color: #fff !important;
}

.system-switcher .ant-select-arrow {
  color: rgba(255, 255, 255, 0.7) !important;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-subtitle {
  color: rgba(255, 255, 255, 0.45);
  font-size: 12px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.header-btn-text {
  color: rgba(255, 255, 255, 0.75) !important;
}

.header-btn-text:hover {
  color: #fff !important;
}

/* ── Body：v2.0 三面板布局 ── */
.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

.panel-left {
  background: #fff;
  border-right: 1px solid #e8e8e8;
  overflow: hidden;
  transition: width 0.15s, min-width 0.15s;
  box-shadow: 2px 0 6px rgba(0, 0, 0, 0.04);
}

.panel-center {
  background: #fafafa;
  overflow: hidden;
  transition: width 0.15s, min-width 0.15s;
}

.panel-right {
  background: #fafafa;
  overflow: hidden;
  border-left: 1px solid #e8e8e8;
  box-shadow: -2px 0 6px rgba(0, 0, 0, 0.04);
}

/* ── 可拖拽分隔条 ── */
.panel-divider {
  width: 4px;
  min-width: 4px;
  background: transparent;
  cursor: col-resize;
  flex-shrink: 0;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.25s;
  z-index: 5;
}

.panel-divider:hover {
  background: #1890ff;
}

.divider-collapse-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 22px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 10px;
  color: #595959;
  background: #fafafa;
  border: 1px solid #e8e8e8;
  border-radius: 3px;
  z-index: 6;
  user-select: none;
  transition: all 0.25s;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.divider-collapse-btn:hover {
  background: #1890ff;
  color: #fff;
  border-color: #1890ff;
  box-shadow: 0 2px 6px rgba(24, 144, 255, 0.3);
}

/* ── 导入向导 ── */
.import-wizard {
  min-height: 300px;
}

.import-step {
  animation: fadeIn 0.3s ease;
}

.mapping-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  gap: 8px;
}

.import-preview {
  margin-top: 12px;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
