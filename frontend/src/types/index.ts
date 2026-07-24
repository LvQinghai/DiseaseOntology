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
  source_name: string
  source_label: string
  target_name: string
  target_label: string
}
