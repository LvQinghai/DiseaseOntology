/** 本体树节点 */
export interface OntologyTreeNode {
  label: string
  name: string
  nodeType: string
  count: number
  elementId?: string
  childCount?: number   // 子类数量，0 或无表示叶节点
  children?: OntologyTreeNode[]
}

export interface OntologyTree {
  roots: OntologyTreeNode[]
}

/** 后端实际返回的本体数据格式 */
export interface OntologyNodeType {
  label: string
  count: number
  properties: Array<{ name: string; sample_value: string }>
  instances: Array<{
    element_id: string
    name: string
    labels: string[]
    child_count: number
  }>
}

export interface OntologyTreeApiResponse {
  node_types: OntologyNodeType[]
  relationship_types: Array<{
    type: string
    count: number
    source_labels: string[]
    target_labels: string[]
    description: string
  }>
}

/** 节点实例 */
export interface NodeInstance {
  name: string
  type: string
  properties: Record<string, unknown>
}

/** 节点详情 */
export interface NodeProperty {
  key: string
  value: unknown
}

export interface NodeRelationship {
  type: string
  direction: 'out' | 'in'
  targetName: string
  targetType: string
  targetElementId?: string
}

export interface NodeDetail {
  name: string
  type: string
  properties: NodeProperty[]
  relationships: NodeRelationship[]
}

/** 关系目录 */
export interface RelationshipCatalogItem {
  type: string
  count: number
  fromTypes: string[]
  toTypes: string[]
  properties: string[]
}

/** 搜索 */
export interface SearchResult {
  nodes: Array<{
    name: string
    type: string
    labels: string[]
  }>
}

/** 图谱 */
export interface GraphNode {
  id: string
  label: string
  type: string
}

export interface GraphEdge {
  id: string
  from: string
  to: string
  label: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

/** 邻域展开 */
export interface NeighborhoodData {
  center: GraphNode
  nodes: GraphNode[]
  edges: GraphEdge[]
}

/** 路径 */
export interface PathData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  length: number
}

/** 问答 */
export interface QueryRequest {
  question: string
  system_id?: string
}

export interface QueryResponse {
  answer: string
  context?: Array<{ name: string; type: string }>
}

// ==================== v2.0 编辑相关类型 ====================

/** 实体响应 */
export interface EntityResponse {
  element_id: string
  labels: string[]
  name: string
  properties: Record<string, unknown>
  relationship_count: number
}

/** 创建实体请求 */
export interface CreateEntityRequest {
  label: string
  name: string
  properties: Record<string, unknown>
}

/** 更新实体请求 */
export interface UpdateEntityRequest {
  name?: string | null
  label?: string | null
  properties?: Record<string, unknown> | null
}

/** 关系响应 */
export interface RelationshipResponse {
  element_id: string
  type: string
  source_id: string
  source_name: string
  target_id: string
  target_name: string
  properties: Record<string, unknown>
}

/** 创建关系请求 */
export interface CreateRelationshipRequest {
  source_element_id?: string
  target_element_id?: string
  type: string
  properties: Record<string, unknown>
}

/** 更新关系请求 */
export interface UpdateRelationshipRequest {
  properties?: Record<string, unknown> | null
  source_element_id?: string | null
  target_element_id?: string | null
  type?: string | null
}

/** 节点搜索结果 */
export interface NodeSearchResult {
  element_id: string
  name: string
  labels: string[]
}

/** 可用标签 */
export interface AvailableLabelsResponse {
  labels: string[]
}

/** 可用关系类型 */
export interface AvailableRelationshipsResponse {
  relationship_types: string[]
}

// ==================== v2.0 删除校验 ====================

/** 关系简要信息（删除校验用） */
export interface RelationshipBrief {
  element_id: string
  type: string
  direction: 'incoming' | 'outgoing'
  other_node_name: string
  other_node_element_id: string
  other_node_label: string
}

/** 删除校验结果 */
export interface DeletionCheckResult {
  can_delete: boolean
  name: string
  relationship_count: number
  relationships: RelationshipBrief[]
  message: string
}

/** 关系实例摘要（编辑器中展示所有源-目标对） */
export interface RelationshipInstanceSummary {
  element_id: string
  source_id: string
  source_name: string
  source_label: string
  target_id: string
  target_name: string
  target_label: string
}

// ==================== v3.0 多系统管理 ====================

/** 系统信息 */
export interface SystemInfo {
  system_id: string
  prefix: string
  name: string
  description: string
  node_count: number
  relationship_count: number
  created_at: string
  updated_at: string
  import_source: string
}

// ==================== v3.0 数据导入 ====================

/** 数据库连接 */
export interface DBConnection {
  db_type: 'mysql' | 'postgresql' | 'mssql' | 'oracle' | 'sqlite'
  host: string
  port: number
  database: string
  user: string
  password: string
}

/** 数据库表结构 */
export interface DBTableInfo {
  name: string
  columns: Array<{ name: string; type: string }>
}

/** 表映射配置 */
export interface TableMapping {
  source_table: string
  source_column: string
  target_label: string
}

/** 关系映射配置 */
export interface RelationshipMapping {
  source_table: string
  source_column: string
  target_table: string
  target_column: string
  relationship_type: string
}

/** 导入预览数据 */
export interface ImportPreviewData {
  entities: Array<Record<string, string>>
  relationships: Array<Record<string, string>>
  total_entities: number
  total_relationships: number
}

/** 导入结果 */
export interface ImportResult {
  success: boolean
  system_id: string
  system_name: string
  entities_created: number
  relationships_created: number
  message: string
  errors: string[]
}

// ==================== v3.5 Sheet 检测 ====================

/** Sheet 信息 */
export interface SheetInfo {
  name: string
  type: 'entity' | 'relationship' | 'unknown'
  headers: string[]
  row_count: number
}

/** Sheet 检测结果 */
export interface SheetDetectionResult {
  entity_sheet: string | null
  relationship_sheet: string | null
  sheets: SheetInfo[]
  unmatched: string[]
  errors: string[]
}

// ==================== v3.5 数据验证 ====================

/** 验证严重等级 */
export type ValidationSeverity = 'error' | 'warning' | 'info'

/** 单个验证问题 */
export interface ValidationIssue {
  severity: ValidationSeverity
  code: string
  message: string
  sheet_type: string
  row_index: number | null
  field: string | null
  detail: Record<string, unknown> | null
}

/** v3.5 实体/关系预览项 */
export interface EntityPreviewItem {
  label: string
  name: string
  properties: Record<string, unknown>
  _row?: number
}

export interface RelationshipPreviewItem {
  source_name: string
  type: string
  target_name: string
  properties: Record<string, unknown>
  _row?: number
}

/** 冲突实体 */
export interface ConflictEntity {
  label: string
  name: string
  existing_props: Record<string, unknown>
  new_props: Record<string, unknown>
  row_index?: number
}

/** 冲突关系 */
export interface ConflictRelationship {
  source_name: string
  type: string
  target_name: string
  row_index?: number
  existing_element_id?: string
}

/** 验证报告 */
export interface DetectionMapping {
  sheet_name: string
  row_count: number
  column_mapping: Record<string, string>  // {原始表头: 标准字段名 or '属性'}
}

export interface DetectionSummary {
  entity_sheet: DetectionMapping | null
  relationship_sheet: DetectionMapping | null
  unmatched_sheets: string[]
}

export interface ValidationReport {
  is_valid: boolean
  entity_count: number
  relationship_count: number
  error_count: number
  warning_count: number
  issues: ValidationIssue[]
  preview: {
    entities: EntityPreviewItem[]
    relationships: RelationshipPreviewItem[]
    entity_count: number
    relationship_count: number
  }
  conflict_entities: ConflictEntity[]
  conflict_relationships: ConflictRelationship[]
  detection_summary?: DetectionSummary
}

// ==================== v3.5 Cypher 预览 ====================

export interface CypherPreviewItem {
  statement: string
  description: string
}

export interface CypherPreview {
  entity_cypher: CypherPreviewItem[]
  relationship_cypher: CypherPreviewItem[]
  total_entity_statements: number
  total_relationship_statements: number
  total_operations: number
}

// ==================== v3.5 执行结果 ====================

export interface ExecuteResult {
  success: boolean
  entities_created: number
  relationships_created: number
  snapshot_id: string | null
  backup_available: boolean
  errors: string[]
  message: string
}

// ==================== v3.5 备份快照 ====================

export interface BackupSnapshot {
  snapshot_id: string
  prefix: string
  created_at: string
  node_count: number
  relationship_count: number
  file_size: number
}

// ==================== v3.6 关系语义 ====================

/** 单条关系语义 */
export interface RelationSemanticInfo {
  id: number
  prefix: string
  rel_type: string
  display_name: string
  description: string
  source_hint: string
  target_hint: string
  cardinality: string      // one_to_one / one_to_many / many_to_many
  symmetry: string          // symmetric / asymmetric / reflexive
  transitivity: string      // transitive / intransitive / none
  created_at: string
  updated_at: string
}

/** 创建/更新关系语义请求 */
export interface UpsertRelationSemanticRequest {
  rel_type: string
  display_name: string
  description: string
  source_hint: string
  target_hint: string
  cardinality: string
  symmetry: string
  transitivity: string
}

/** 系统的全部语义配置 */
export interface SystemSemanticsResponse {
  prefix: string
  domain_description: string
  semantics: RelationSemanticInfo[]
}

/** 基数选项 */
export const CARDINALITY_OPTIONS = [
  { value: '', label: '未指定' },
  { value: 'one_to_one', label: '一对一 (1:1)' },
  { value: 'one_to_many', label: '一对多 (1:N)' },
  { value: 'many_to_many', label: '多对多 (M:N)' },
]

/** 对称性选项 */
export const SYMMETRY_OPTIONS = [
  { value: '', label: '未指定' },
  { value: 'symmetric', label: '对称 (A→B 则 B→A)' },
  { value: 'asymmetric', label: '非对称 (A→B 不一定 B→A)' },
  { value: 'reflexive', label: '自反 (A→A)' },
]

/** 传递性选项 */
export const TRANSITIVITY_OPTIONS = [
  { value: '', label: '未指定' },
  { value: 'transitive', label: '传递 (A→B, B→C 则 A→C)' },
  { value: 'intransitive', label: '非传递' },
  { value: 'none', label: '不适用' },
]
