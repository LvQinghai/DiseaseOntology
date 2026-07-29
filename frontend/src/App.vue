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
          <a-button type="primary" size="small" shape="round" @click="onOpenImportWizard">
            <template #icon><ImportOutlined /></template>
            导入新数据
          </a-button>

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

    <!-- ==================== v3.5 导入向导（5步引导式） ==================== -->
    <a-modal
      :open="store.importWizardVisible"
      title="导入数据向导"
      width="760px"
      :footer="null"
      :maskClosable="false"
      @cancel="onCloseImportWizard"
    >
      <!-- 横向步骤指示器 -->
      <a-steps :current="store.importStep" size="small" style="margin-bottom:24px">
        <a-step title="选择来源" />
        <a-step title="导入模式" />
        <a-step :title="store.importMode === 'new' ? '配置新系统' : '选择目标系统'" />
        <a-step :title="store.importSource === 'excel' ? '上传文件' : '配置数据源'" />
        <a-step title="预览确认" />
      </a-steps>

      <!-- Step 0: 选择来源 -->
      <div v-if="store.importStep === 0" class="import-step-body">
        <a-row :gutter="16">
          <a-col :span="12">
            <div
              class="import-card"
              :class="{ 'import-card--selected': store.importSource === 'excel' }"
              @click="store.importSource = 'excel'"
            >
              <FileExcelOutlined style="font-size:48px;color:#52c41a" />
              <p class="import-card__title">从 Excel 导入</p>
              <p class="import-card__hint">上传 .xlsx / .xls 文件</p>
            </div>
          </a-col>
          <a-col :span="12">
            <div
              class="import-card"
              :class="{ 'import-card--selected': store.importSource === 'database' }"
              @click="store.importSource = 'database'"
            >
              <DatabaseOutlined style="font-size:48px;color:#1890ff" />
              <p class="import-card__title">从数据库导入</p>
              <p class="import-card__hint">MySQL / PostgreSQL / SQLite 等</p>
            </div>
          </a-col>
        </a-row>
        <div class="import-step__actions">
          <a-button type="primary" @click="goToStep(1)">下一步</a-button>
        </div>
      </div>

      <!-- Step 1: 选择模式 -->
      <div v-if="store.importStep === 1" class="import-step-body">
        <a-row :gutter="16">
          <a-col :span="12">
            <div
              class="import-card"
              :class="{ 'import-card--selected': store.importMode === 'new' }"
              @click="store.importMode = 'new'"
            >
              <PlusCircleOutlined style="font-size:48px;color:#1677ff" />
              <p class="import-card__title">创建全新图谱</p>
              <p class="import-card__hint">
                在 Neo4j 中建立独立的图谱系统<br/>
                使用独立的前缀区分不同图谱
              </p>
            </div>
          </a-col>
          <a-col :span="12">
            <div
              class="import-card"
              :class="{ 'import-card--selected': store.importMode === 'append' }"
              @click="store.importMode = 'append'"
            >
              <ApartmentOutlined style="font-size:48px;color:#fa8c16" />
              <p class="import-card__title">追加到已有图谱</p>
              <p class="import-card__hint">
                将新数据合并到现有图谱中<br/>
                共享同一前缀和节点体系
              </p>
            </div>
          </a-col>
        </a-row>
        <div class="import-step__actions">
          <a-button @click="goToStep(0)">上一步</a-button>
          <a-button type="primary" style="margin-left:8px" @click="goToStep(2)">下一步</a-button>
        </div>
      </div>

      <!-- Step 2A: 新建系统配置 -->
      <div v-if="store.importStep === 2 && store.importMode === 'new'" class="import-step-body">
        <a-form layout="vertical">
          <a-form-item label="图谱名称" required>
            <a-input
              v-model:value="store.newSystemName"
              placeholder="例如：汽车零件本体知识图谱"
              :maxlength="50"
            />
          </a-form-item>
          <a-form-item label="区分前缀" required>
            <a-input
              v-model:value="store.newSystemPrefix"
              placeholder="例如：CAR"
              style="width:200px"
              :maxlength="3"
              :status="store.newSystemPrefix.trim() ? (isPrefixValid ? '' : 'error') : ''"
              @input="onPrefixInput"
            />
            <span v-if="store.newSystemPrefix.trim() && !isPrefixValid" style="color:#ff4d4f;font-size:12px;display:block;margin-top:2px">
              前缀必须为 3 位大写英文字母（A-Z），下划线由系统自动添加
            </span>
            <span v-if="isPrefixValid" style="color:#52c41a;font-size:12px;display:block;margin-top:2px">
              实际标签前缀将自动生成为：<a-tag color="blue" size="small">{{ store.newSystemPrefix.toUpperCase() }}_</a-tag>
            </span>
            <a-alert type="info" show-icon style="margin-top:8px">
              <template #message>
                <strong>什么是前缀？</strong><br/>
                由于 Neo4j 社区版不支持多数据库，因此使用标签前缀来区分不同图谱的节点和关系。<br/>
                请输入 <strong>3 位大写字母</strong>（如 <code>CAR</code>、<code>MED</code>），系统会在写入 Neo4j 时自动追加下划线 <code>_</code>。<br/>
                例如输入 <code>CAR</code>，实体的标签将自动命名为 <code>CAR_Disease</code>、<code>CAR_Drug</code> 等。<br/>
                <strong>不同图谱的前缀不能相同，且创建后不可修改。</strong>
              </template>
            </a-alert>
          </a-form-item>
          <a-form-item label="图谱描述（选填）">
            <a-textarea
              v-model:value="store.newSystemDesc"
              placeholder="简要描述该图谱的内容和用途"
              :rows="2"
              :maxlength="200"
            />
          </a-form-item>
        </a-form>
        <div class="import-step__actions">
          <a-button @click="goToStep(1)">上一步</a-button>
          <a-button
            type="primary"
            :disabled="!store.newSystemName.trim() || !isPrefixValid"
            style="margin-left:8px"
            @click="goToStep(3)"
          >
            下一步
          </a-button>
        </div>
      </div>

      <!-- Step 2B: 选择目标系统 -->
      <div v-if="store.importStep === 2 && store.importMode === 'append'" class="import-step-body">
        <a-form layout="vertical">
          <a-form-item label="目标图谱" required>
            <a-select
              v-model:value="store.appendTargetSystemId"
              placeholder="选择要追加的系统"
              style="width:100%"
            >
              <a-select-option
                v-for="sys in store.systemList"
                :key="sys.system_id"
                :value="sys.system_id"
              >
                <span>{{ sys.name }}</span>
                <a-tag color="blue" style="margin-left:8px">前缀: {{ sys.prefix }}</a-tag>
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-alert v-if="selectedTargetSystem" type="info" show-icon>
            <template #message>
              该图谱当前有 <strong>{{ selectedTargetSystem.node_count }}</strong> 个实体，
              <strong>{{ selectedTargetSystem.relationship_count }}</strong> 条关系。<br/>
              导入的新数据将使用该系统的标签前缀
              <a-tag color="blue" size="small">{{ selectedTargetSystem.prefix }}</a-tag>
              写入 Neo4j。
            </template>
          </a-alert>
        </a-form>
        <div class="import-step__actions">
          <a-button @click="goToStep(1)">上一步</a-button>
          <a-button
            type="primary"
            :disabled="!store.appendTargetSystemId"
            style="margin-left:8px"
            @click="goToStep(3)"
          >
            下一步
          </a-button>
        </div>
      </div>

      <!-- Step 3: 上传文件 / 配置数据库 -->
      <div v-if="store.importStep === 3" class="import-step-body">
        <div v-if="store.importSource === 'excel'">
          <a-upload-dragger
            :before-upload="handleExcelUpload"
            :show-upload-list="false"
            accept=".xlsx,.xls"
          >
            <p class="ant-upload-drag-icon"><InboxOutlined style="font-size:48px;color:#1677ff" /></p>
            <p class="ant-upload-text">点击或拖拽 Excel 文件到此处</p>
            <p class="ant-upload-hint">支持 .xlsx / .xls 格式</p>
          </a-upload-dragger>
          <div v-if="excelFile" style="margin-top:12px">
            <a-alert :message="`已加载: ${excelFile.name}`" type="success" show-icon />
          </div>
          <div v-if="excelError" style="margin-top:12px">
            <a-alert :message="excelError" type="error" show-icon />
          </div>
        </div>

        <div v-if="store.importSource === 'database'">
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
          <a-button type="primary" :loading="dbConnecting" @click="onTestConnection">
            测试连接并获取表结构
          </a-button>
          <div v-if="dbConError" style="margin-top:12px">
            <a-alert :message="dbConError" type="error" show-icon />
          </div>
          <a-alert
            v-if="dbTables.length > 0"
            :message="`连接成功！发现 ${dbTables.length} 张表`"
            type="success" show-icon
            style="margin-top:12px"
          />
        </div>

        <div class="import-step__actions">
          <a-button @click="goToStep(2)">上一步</a-button>
          <a-button
            type="primary"
            style="margin-left:8px"
            :disabled="!canProceedFromStep3"
            :loading="validating"
            @click="onGoToValidation"
          >
            下一步（验证数据）
          </a-button>
        </div>
      </div>

      <!-- ★ v3.5 Step 4: 数据验证报告 -->
      <div v-if="store.importStep === 4" class="import-step-body">
        <a-spin :spinning="validating" tip="正在验证数据...">
          <div v-if="store.validationReport">
            <!-- 验证统计 -->
            <a-row :gutter="12" style="margin-bottom:12px">
              <a-col :span="6">
                <a-statistic title="实体" :value="store.validationReport.entity_count" value-style="color:#1677ff" />
              </a-col>
              <a-col :span="6">
                <a-statistic title="关系" :value="store.validationReport.relationship_count" value-style="color:#fa8c16" />
              </a-col>
              <a-col :span="6">
                <a-statistic
                  title="错误"
                  :value="store.validationReport.error_count"
                  :value-style="{ color: store.validationReport.error_count > 0 ? '#ff4d4f' : '#52c41a' }"
                />
              </a-col>
              <a-col :span="6">
                <a-statistic
                  title="警告"
                  :value="store.validationReport.warning_count"
                  :value-style="{ color: store.validationReport.warning_count > 0 ? '#faad14' : '#52c41a' }"
                />
              </a-col>
            </a-row>

            <!-- 检测摘要：Sheet 识别与列映射结果 -->
            <a-alert
              v-if="store.validationReport.detection_summary"
              type="info"
              show-icon
              style="margin-bottom:12px"
            >
              <template #message>
                <span style="font-weight:600">Sheet 识别与列映射结果</span>
              </template>
              <template #description>
                <div v-if="store.validationReport.detection_summary.entity_sheet" style="margin-bottom:6px">
                  <strong>实体 Sheet:</strong>
                  {{ store.validationReport.detection_summary.entity_sheet.sheet_name }}
                  ({{ store.validationReport.detection_summary.entity_sheet.row_count }} 行)
                  <span v-for="(target, source) in store.validationReport.detection_summary.entity_sheet.column_mapping" :key="source" style="margin-left:6px;font-size:12px">
                    {{ source }} <a-tag :color="target === '属性' ? 'default' : 'blue'" style="margin:0">{{ target }}</a-tag>
                  </span>
                </div>
                <div v-if="store.validationReport.detection_summary.relationship_sheet" style="margin-bottom:6px">
                  <strong>关系 Sheet:</strong>
                  {{ store.validationReport.detection_summary.relationship_sheet.sheet_name }}
                  ({{ store.validationReport.detection_summary.relationship_sheet.row_count }} 行)
                  <span v-for="(target, source) in store.validationReport.detection_summary.relationship_sheet.column_mapping" :key="source" style="margin-left:6px;font-size:12px">
                    {{ source }} <a-tag :color="target === '属性' ? 'default' : 'blue'" style="margin:0">{{ target }}</a-tag>
                  </span>
                </div>
                <div v-if="store.validationReport.detection_summary.unmatched_sheets.length > 0">
                  <strong style="color:#faad14">未识别的 Sheet:</strong>
                  <a-tag v-for="s in store.validationReport.detection_summary.unmatched_sheets" :key="s" color="orange" style="margin-left:4px">{{ s }}</a-tag>
                </div>
              </template>
            </a-alert>

            <!-- 验证问题列表 -->
            <div v-if="store.validationReport.issues.length > 0" style="margin-bottom:16px;max-height:220px;overflow-y:auto">
              <a-alert
                v-for="(issue, idx) in store.validationReport.issues"
                :key="idx"
                :type="issue.severity === 'error' ? 'error' : issue.severity === 'warning' ? 'warning' : 'info'"
                :message="issue.message"
                :show-icon="true"
                style="margin-bottom:4px"
              >
                <template #description>
                  <span style="font-size:12px">
                    [{{ issue.sheet_type === 'entity' ? '实体' : '关系' }}]
                    第 {{ issue.row_index }} 行 · {{ issue.field }}
                  </span>
                </template>
              </a-alert>
            </div>

            <!-- 冲突检测（追加模式） -->
            <a-alert
              v-if="store.importMode === 'append' && (store.validationReport.conflict_entities.length > 0 || store.validationReport.conflict_relationships.length > 0)"
              type="warning"
              show-icon
              style="margin-bottom:12px"
            >
              <template #message>
                检测到与已有图谱的冲突:
                <span v-if="store.validationReport.conflict_entities.length">{{ store.validationReport.conflict_entities.length }} 个实体已存在，</span>
                <span v-if="store.validationReport.conflict_relationships.length">{{ store.validationReport.conflict_relationships.length }} 条关系已存在。</span>
                系统将使用 MERGE 模式自动合并数据。
              </template>
            </a-alert>

            <!-- 数据预览 -->
            <h4 style="margin-bottom:4px">数据预览（前 20 条）：</h4>
            <a-table
              v-if="store.validationReport.preview.entities.length > 0"
              :data-source="store.validationReport.preview.entities"
              :columns="previewEntityColumns"
              size="small"
              :pagination="false"
              style="margin-bottom:12px"
              :scroll="{ y: 200 }"
            />
          </div>
          <a-empty v-if="!store.validationReport && !validating" description="验证结果加载失败" />
        </a-spin>

        <div class="import-step__actions">
          <a-button @click="goToStep(3)">上一步</a-button>
          <a-button
            type="primary"
            style="margin-left:8px"
            :disabled="!store.validationReport || !store.validationReport.is_valid"
            @click="goToStep(5)"
          >
            确认并继续
          </a-button>
        </div>
      </div>

      <!-- ★ v3.5 Step 5: 确认导入（含备份提示） -->
      <div v-if="store.importStep === 5" class="import-step-body">
        <!-- 导入摘要 -->
        <a-descriptions bordered size="small" :column="2" style="margin-bottom:16px">
          <a-descriptions-item label="导入模式">
            <a-tag :color="store.importMode === 'new' ? 'blue' : 'orange'">
              {{ store.importMode === 'new' ? '创建全新图谱' : '追加到已有图谱' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="数据来源">
            <a-tag color="green">{{ store.importSource === 'excel' ? 'Excel 文件' : dbConn.db_type.toUpperCase() }}</a-tag>
          </a-descriptions-item>
          <template v-if="store.importMode === 'new'">
            <a-descriptions-item label="系统名称">{{ store.newSystemName }}</a-descriptions-item>
            <a-descriptions-item label="标签前缀">
              <a-tag color="blue">{{ store.newSystemPrefix ? normalizePrefixDisplay(store.newSystemPrefix) : '(自动生成)' }}</a-tag>
            </a-descriptions-item>
          </template>
          <template v-else>
            <a-descriptions-item label="目标系统">
              {{ selectedTargetSystem?.name || store.appendTargetSystemId }}
            </a-descriptions-item>
            <a-descriptions-item label="目标前缀">
              <a-tag color="blue">{{ selectedTargetSystem?.prefix }}</a-tag>
            </a-descriptions-item>
          </template>
          <a-descriptions-item label="实体数量">
            <a-tag color="blue">{{ store.validationReport?.entity_count || 0 }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="关系数量">
            <a-tag color="orange">{{ store.validationReport?.relationship_count || 0 }}</a-tag>
          </a-descriptions-item>
        </a-descriptions>

        <!-- 备份提示 -->
        <a-alert
          type="info"
          show-icon
          message="导入前将自动备份当前图谱数据"
          description="系统会在写入前创建数据快照。如导入后发现问题，可通过备份回滚至导入前状态。"
          style="margin-bottom:16px"
        />

        <div class="import-step__actions">
          <a-button @click="goToStep(4)" :disabled="importing || store.executeResult?.success">上一步</a-button>
          <template v-if="store.executeResult?.success">
            <a-button type="primary" disabled style="margin-left:8px" class="header-action-link">
              导入成功
            </a-button>
            <a-button type="primary" style="margin-left:8px" @click="onCloseImportWizard">
              关闭
            </a-button>
          </template>
          <a-button
            v-else
            type="primary"
            :loading="importing"
            style="margin-left:8px"
            @click="onExecuteImport"
          >
            确认导入
          </a-button>
        </div>

        <div v-if="store.executeResult" style="margin-top:16px">
          <a-alert
            v-if="store.executeResult.success"
            :message="store.executeResult.message"
            type="success"
            show-icon
          />
          <a-alert
            v-else
            :message="store.executeResult.errors?.join(', ') || store.executeResult.message"
            type="error"
            show-icon
          />
          <div v-if="store.executeResult.backup_available && store.executeResult.snapshot_id" style="margin-top:8px">
            <a-alert
              type="warning"
              show-icon
              message="如需回滚："
            >
              <template #description>
                <span>备份ID: <a-tag>{{ store.executeResult.snapshot_id }}</a-tag></span>
              </template>
            </a-alert>
          </div>
        </div>
      </div>
    </a-modal>

    <!-- ==================== v3.0 系统管理弹窗 ==================== -->
    <a-modal
      v-model:open="store.systemManagerVisible"
      title="系统管理"
      width="860px"
      :footer="null"
    >
      <a-table
        :data-source="store.systemList"
        :columns="systemColumns"
        :pagination="false"
        size="small"
        row-key="system_id"
        :scroll="{ x: 820 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <span class="sys-name-cell">{{ record.name }}</span>
          </template>
          <template v-else-if="column.key === 'prefix'">
            <a-tag color="blue">{{ record.prefix }}</a-tag>
          </template>
          <template v-else-if="column.key === 'node_count'">
            <a-tag color="blue">{{ record.node_count ?? 0 }}</a-tag>
          </template>
          <template v-else-if="column.key === 'relationship_count'">
            <a-tag color="orange">{{ record.relationship_count ?? 0 }}</a-tag>
          </template>
          <template v-else-if="column.key === 'import_source'">
            <a-tag :color="record.import_source === 'excel' ? 'green' : 'cyan'">
              {{ record.import_source || '—' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button
              type="link"
              danger
              size="small"
              :disabled="record.system_id === 'disease_ontology'"
              @click="onOpenDeleteConfirm(record)"
            >
              删除
            </a-button>
          </template>
        </template>
      </a-table>
    </a-modal>

    <!-- ==================== 删除系统确认弹窗 ==================== -->
    <a-modal
      v-model:open="deleteConfirmVisible"
      title="删除系统确认"
      width="560px"
      :confirm-loading="deleteConfirmLoading"
      :ok-button-props="{ danger: true, disabled: deleteConfirmInput !== deleteConfirmTarget?.name }"
      ok-text="确认删除"
      cancel-text="取消"
      @ok="onConfirmDeleteSystem"
      @cancel="deleteConfirmVisible = false"
    >
      <div v-if="deleteConfirmLoading && !deleteConfirmStats" style="text-align: center; padding: 24px 0">
        <a-spin tip="正在获取系统详细信息..." />
      </div>
      <div v-else-if="deleteConfirmStats">
        <a-alert
          type="warning"
          show-icon
          style="margin-bottom: 16px"
          message="此操作不可逆！将永久删除该系统的所有图谱数据和配置。"
        />

        <a-descriptions :column="2" bordered size="small" style="margin-bottom: 16px">
          <a-descriptions-item label="系统名称">{{ deleteConfirmStats.name }}</a-descriptions-item>
          <a-descriptions-item label="前缀">{{ deleteConfirmStats.prefix }}</a-descriptions-item>
          <a-descriptions-item label="节点总数">
            <a-tag color="blue">{{ deleteConfirmStats.node_count }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="关系总数">
            <a-tag color="orange">{{ deleteConfirmStats.relationship_count }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="关系语义配置">
            <a-tag color="purple">{{ deleteConfirmStats.semantics_count }} 条</a-tag>
          </a-descriptions-item>
        </a-descriptions>

        <!-- 节点标签明细 -->
        <div v-if="deleteConfirmStats.node_labels.length > 0" style="margin-bottom: 12px">
          <div style="font-weight: 600; margin-bottom: 6px; font-size: 13px">节点标签明细</div>
          <div style="display: flex; flex-wrap: wrap; gap: 6px">
            <a-tag v-for="item in deleteConfirmStats.node_labels" :key="item.label" color="blue">
              {{ item.label }}: {{ item.count }}
            </a-tag>
          </div>
        </div>

        <!-- 关系类型明细 -->
        <div v-if="deleteConfirmStats.relationship_types.length > 0" style="margin-bottom: 16px">
          <div style="font-weight: 600; margin-bottom: 6px; font-size: 13px">关系类型明细</div>
          <div style="display: flex; flex-wrap: wrap; gap: 6px">
            <a-tag v-for="item in deleteConfirmStats.relationship_types" :key="item.type" color="orange">
              {{ item.type }}: {{ item.count }}
            </a-tag>
          </div>
        </div>

        <a-divider style="margin: 12px 0" />

        <div style="margin-bottom: 8px; font-size: 13px">
          请输入系统名称 <strong style="color: #ff4d4f">{{ deleteConfirmStats.name }}</strong> 以确认删除：
        </div>
        <a-input
          v-model:value="deleteConfirmInput"
          placeholder="请输入系统名称"
          :status="deleteConfirmInput && deleteConfirmInput !== deleteConfirmTarget?.name ? 'error' : undefined"
        />
      </div>
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
  PlusCircleOutlined,
  ApartmentOutlined,
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
  fetchSystemStats,
  testDBConnection,
  getDBTables,
  previewDBImport,
  importFromDB,
  downloadTemplate,
  // v3.5
  validateExcel,
  validateExcelAppend,
  executeImport,
} from '@/api'
import type {
  DBConnection,
  DBTableInfo,
  TableMapping,
  RelationshipMapping,
  ImportPreviewData,
  ImportResult,
  ExecuteResult,
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
  { title: '系统名称', dataIndex: 'name', key: 'name', width: 200, ellipsis: true },
  { title: '系统ID', dataIndex: 'system_id', key: 'system_id', width: 160, ellipsis: true },
  { title: '前缀', dataIndex: 'prefix', key: 'prefix', width: 80, align: 'center' as const },
  { title: '实体数', dataIndex: 'node_count', key: 'node_count', width: 80, align: 'center' as const },
  { title: '关系数', dataIndex: 'relationship_count', key: 'relationship_count', width: 80, align: 'center' as const },
  { title: '来源', dataIndex: 'import_source', key: 'import_source', width: 100, align: 'center' as const },
  { title: '操作', key: 'action', width: 80, align: 'center' as const, fixed: 'right' as const },
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

// ==================== 删除系统确认 ====================

const deleteConfirmVisible = ref(false)
const deleteConfirmLoading = ref(false)
const deleteConfirmTarget = ref<{ system_id: string; name: string } | null>(null)
const deleteConfirmStats = ref<{
  system_id: string
  name: string
  prefix: string
  node_count: number
  relationship_count: number
  node_labels: { label: string; count: number }[]
  relationship_types: { type: string; count: number }[]
  semantics_count: number
} | null>(null)
const deleteConfirmInput = ref('')

async function onOpenDeleteConfirm(record: { system_id: string; name: string }) {
  deleteConfirmTarget.value = record
  deleteConfirmStats.value = null
  deleteConfirmInput.value = ''
  deleteConfirmVisible.value = true
  deleteConfirmLoading.value = true
  try {
    deleteConfirmStats.value = await fetchSystemStats(record.system_id)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '获取系统统计信息失败')
    deleteConfirmVisible.value = false
  } finally {
    deleteConfirmLoading.value = false
  }
}

async function onConfirmDeleteSystem() {
  if (!deleteConfirmTarget.value) return
  if (deleteConfirmInput.value !== deleteConfirmTarget.value.name) {
    message.warning('请输入正确的系统名称以确认删除')
    return
  }
  deleteConfirmLoading.value = true
  try {
    const result = await deleteSystem(deleteConfirmTarget.value.system_id)
    store.removeSystem(deleteConfirmTarget.value.system_id)
    message.success(
      `系统已删除：${result.deleted_nodes} 个节点、${result.deleted_relationships} 条关系、${result.deleted_semantics} 条语义配置`,
    )
    store.triggerTreeRefresh()
    deleteConfirmVisible.value = false
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '删除失败')
  } finally {
    deleteConfirmLoading.value = false
  }
}

// ==================== v3.5 导入向导 ====================

const importing = ref(false)
const validating = ref(false)
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

/** v3.5: 选中的目标系统（追加模式） */
const selectedTargetSystem = computed(() =>
  store.systemList.find(s => s.system_id === store.appendTargetSystemId)
)

/** v3.5: Step3 到 Step4 的前置条件 */
const canProceedFromStep3 = computed(() => {
  if (store.importSource === 'excel') return excelFile.value !== null
  return dbTables.value.length > 0
})

const previewSampleE = computed(() => {
  const src = store.importSource === 'excel' ? excelPreview.value : dbPreview.value
  return src?.entities?.slice(0, 5) || []
})

const previewEntityColumns = computed(() => {
  // v3.5: 优先使用 validation report 中的预览数据自动生成列
  const entities = store.validationReport?.preview?.entities
  if (entities && entities.length > 0) {
    const cols: any[] = [
      { title: '行号', dataIndex: '_row', key: '_row', width: 60 },
      { title: '标签', dataIndex: 'label', key: 'label', width: 100 },
      { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
    ]
    // 动态追加属性列（从第一个实体的 properties 中提取 key）
    const first = entities[0]
    if (first.properties && typeof first.properties === 'object' && Object.keys(first.properties as Record<string, unknown>).length > 0) {
      for (const k of Object.keys(first.properties as Record<string, unknown>)) {
        cols.push({
          title: k,
          key: `prop_${k}`,
          ellipsis: true,
          customRender: ({ record }: any) => record?.properties?.[k] ?? '',
        })
      }
    }
    return cols
  }

  // fallback: 旧版预览数据（v3.0）
  if (previewSampleE.value.length === 0) return []
  return Object.keys(previewSampleE.value[0]).map(k => ({ title: k, dataIndex: k, key: k }))
})

/** v3.5: 前缀验证：必须为 3 位大写字母 */
const isPrefixValid = computed(() => {
  const val = store.newSystemPrefix.trim()
  if (!val) return false
  return /^[A-Z]{3}$/.test(val)
})

/** 输入前缀时自动转为大写 */
function onPrefixInput(e: Event) {
  const target = e.target as HTMLInputElement
  if (target) {
    target.value = target.value.toUpperCase().replace(/[^A-Z]/g, '')
    store.newSystemPrefix = target.value
  }
}

/** 将前缀转为展示格式（追加下划线） */
function normalizePrefixDisplay(prefix: string) {
  const trimmed = prefix.trim().toUpperCase()
  return trimmed.endsWith('_') ? trimmed : trimmed + '_'
}

/** v3.5: 打开导入向导（默认从 Excel 开始） */
function onOpenImportWizard() {
  resetImportState()
  store.openImportWizard('excel')
}

/** v3.5: 关闭导入向导（用于 X 按钮和遮罩） */
function onCloseImportWizard() {
  store.closeImportWizard()
}

/** v3.5: 导航到指定步骤 */
function goToStep(step: number) {
  store.importStep = step
}

/** v3.5: 从 Step3 进入验证步骤 */
async function onGoToValidation() {
  if (store.importSource !== 'excel' || !excelFile.value) {
    // 数据库来源直接跳确认
    store.importStep = 5
    return
  }

  validating.value = true
  try {
    if (store.importMode === 'append' && store.appendTargetSystemId) {
      store.validationReport = await validateExcelAppend(excelFile.value, store.appendTargetSystemId)
    } else {
      store.validationReport = await validateExcel(excelFile.value)
    }
    store.importStep = 4
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (detail) {
      message.error(typeof detail === 'string' ? detail : '验证失败: ' + JSON.stringify(detail))
    } else if (e?.response?.status === 500) {
      message.error('服务器内部错误，请检查后端服务是否正常')
    } else {
      message.error('验证失败，请检查文件格式或网络连接')
    }
  } finally {
    validating.value = false
  }
}

/** v3.5: 执行导入（含备份） */
async function onExecuteImport() {
  importing.value = true
  store.executeResult = null
  try {
    if (store.importSource === 'excel' && excelFile.value) {
      // ★ v3.5: Excel 导入（含验证+备份）
      const prefix = store.importMode === 'new'
        ? store.newSystemPrefix
        : (selectedTargetSystem.value?.prefix || '')

      const result: ExecuteResult = await executeImport(
        excelFile.value,
        store.importMode,
        prefix,
        store.importMode === 'new' ? store.newSystemName : '',
        store.importMode === 'new' ? store.newSystemDesc : '',
        store.importMode === 'append' ? store.appendTargetSystemId : '',
        'MERGE',
      )
      store.executeResult = result
      if (result.success && result.snapshot_id) {
        store.lastSnapshotId = result.snapshot_id
      }
      if (result.success) {
        message.success(result.message)
        await refreshSystemList()
      } else {
        message.error(result.message)
      }
    } else {
      // ★ DB 导入（保持原有流程）
      if (store.importMode === 'new') {
        importResult.value = await importFromDB(
          dbConn.value,
          entityMappings.value.filter(m => m.source_table),
          store.newSystemName.trim(),
          store.newSystemDesc.trim(),
          store.newSystemPrefix.trim(),
          relationshipMappings.value.filter(m => m.source_table) || undefined,
        )
      } else {
        const { appendFromDB } = await import('@/api')
        importResult.value = await appendFromDB(
          dbConn.value,
          entityMappings.value.filter(m => m.source_table),
          store.appendTargetSystemId,
          relationshipMappings.value.filter(m => m.source_table) || undefined,
        )
      }
      if (importResult.value?.success) {
        message.success('导入成功！')
        await refreshSystemList()
        store.setCurrentSystem(importResult.value.system_id)
        store.triggerTreeRefresh()
      }
    }
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}

function resetImportState() {
  store.importStep = 0
  importing.value = false
  validating.value = false
  importResult.value = null
  store.validationReport = null
  store.executeResult = null
  store.lastSnapshotId = null
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
}

async function handleExcelUpload(file: File) {
  excelFile.value = file
  excelError.value = ''
  // v3.5: 不在上传时预览，验证在 Step4 统一触发
  return false  // 阻止自动上传，由向导控制流程
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
    store.importStep = 5  // v3.5: 数据库预览后直接到确认页
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '预览失败')
  } finally {
    dbPreviewing.value = false
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

/* ── v3.5 导入向导 ── */
.import-step-body {
  min-height: 280px;
  animation: fadeIn 0.3s ease;
}

.import-step__actions {
  margin-top: 20px;
  text-align: right;
}

/* 卡片选择器（来源选择 + 模式选择） */
.import-card {
  text-align: center;
  padding: 32px 16px;
  border: 2px solid #e8e8e8;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.25s ease;
  background: #fafafa;
}
.import-card:hover {
  border-color: #1677ff;
  background: #f0f5ff;
}
.import-card--selected {
  border-color: #1677ff;
  background: #e6f4ff;
  box-shadow: 0 0 0 2px rgba(22, 119, 255, 0.15);
}
.import-card__title {
  font-size: 15px;
  font-weight: 600;
  margin: 12px 0 4px;
  color: #1a1a1a;
}
.import-card__hint {
  font-size: 12px;
  color: #999;
  line-height: 1.6;
}

/* 数据库映射配置 */
.mapping-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  gap: 8px;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── 系统管理弹窗表格 ── */
.sys-name-cell {
  white-space: nowrap;
  font-weight: 500;
  color: #1a1a1a;
}
</style>
