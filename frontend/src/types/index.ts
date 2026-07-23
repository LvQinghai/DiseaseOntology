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
