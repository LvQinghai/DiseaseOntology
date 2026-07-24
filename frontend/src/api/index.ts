import axios from 'axios'
import type {
  OntologyTree,
  OntologyTreeNode,
  OntologyTreeApiResponse,
  NodeDetail,
  RelationshipCatalogItem,
  SearchResult,
  GraphData,
  NeighborhoodData,
  PathData,
  QueryRequest,
  QueryResponse,
  EntityResponse,
  CreateEntityRequest,
  UpdateEntityRequest,
  RelationshipResponse,
  CreateRelationshipRequest,
  UpdateRelationshipRequest,
  NodeSearchResult,
  AvailableLabelsResponse,
  AvailableRelationshipsResponse,
  RelationshipInstanceSummary,
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// ===== 本体浏览 =====

export async function fetchOntologyTree(): Promise<OntologyTree> {
  const { data } = await api.get<OntologyTreeApiResponse>('/ontology/tree')

  // 本体类型 → 树节点
  const nodeTypeRoots = (data.node_types || []).map((nt) => ({
    label: nt.label,
    name: nt.label,
    nodeType: nt.label,
    count: nt.count,
    elementId: '',
    children: (nt.instances || []).map((inst) => ({
      label: inst.name,
      name: inst.name,
      nodeType: nt.label,
      count: 0,
      elementId: inst.element_id,
      childCount: inst.child_count ?? 0,
    })),
  }))

  // 关系类型 → 树节点（更简洁的叶子节点）
  if (data.relationship_types && data.relationship_types.length > 0) {
    const relChildren: OntologyTreeNode[] = data.relationship_types.map((rt) => ({
      label: `${rt.type} (${rt.count})`,
      name: rt.type,
      nodeType: '__RELATIONSHIP__',
      count: rt.count,
      elementId: '',
      children: undefined,
    }))

    const relationshipRoot: OntologyTreeNode = {
      label: '关系',
      name: '关系',
      nodeType: '__RELATIONSHIP_ROOT__',
      count: data.relationship_types.length,
      elementId: '',
      children: relChildren,
    }

    return { roots: [...nodeTypeRoots, relationshipRoot] }
  }

  return { roots: nodeTypeRoots }
}

export async function fetchNodeDetail(elementId: string): Promise<NodeDetail> {
  const { data } = await api.get(`/ontology/nodes/${encodeURIComponent(elementId)}`)
  // 转换后端格式为前端 NodeDetail 格式
  const props = data.properties || {}
  const incoming = (data.incoming_relationships || []).map((r: any) => ({
    type: r.type,
    direction: 'in' as const,
    targetName: r.target_name,
    targetType: r.target_label,
    targetElementId: r.target_element_id,
  }))
  const outgoing = (data.outgoing_relationships || []).map((r: any) => ({
    type: r.type,
    direction: 'out' as const,
    targetName: r.target_name,
    targetType: r.target_label,
    targetElementId: r.target_element_id,
  }))
  // v2.0: 将 name 属性排到最前面
  const propEntries = Object.entries(props)
    .filter(([k]) => k !== 'name')
    .map(([key, value]) => ({ key, value }))
  if (props.name !== undefined) {
    propEntries.unshift({ key: 'name', value: props.name })
  }
  return {
    name: props.name || (data.labels && data.labels[0]) || '',
    type: (data.labels && data.labels[0]) || '',
    properties: propEntries,
    relationships: [...incoming, ...outgoing],
  }
}

export async function fetchRelationshipCatalog(): Promise<RelationshipCatalogItem[]> {
  const { data } = await api.get('/ontology/relationships')
  return data
}

export async function fetchSearch(keyword: string): Promise<SearchResult> {
  const { data } = await api.get('/ontology/search', { params: { keyword } })
  return data
}

// ===== 树形懒加载 =====

export async function fetchSubclassChildren(elementId: string): Promise<{
  element_id: string
  name: string
  labels: string[]
  child_count: number
}[]> {
  const { data } = await api.get(`/ontology/nodes/${encodeURIComponent(elementId)}/subclasses`)
  return data
}

// ===== 图谱 =====

export async function fetchGraphOverview(): Promise<GraphData> {
  const { data } = await api.get('/graph/overview')
  return data
}

export async function fetchNeighborhood(
  elementId: string,
  depth = 1,
): Promise<NeighborhoodData> {
  const { data } = await api.get(`/graph/neighbors/${encodeURIComponent(elementId)}`, {
    params: { depth },
  })
  return data
}

export async function fetchShortestPath(
  source: string,
  target: string,
): Promise<PathData> {
  const { data } = await api.get('/graph/path', {
    params: { source, target },
  })
  return data
}

// ===== 智能问答 =====

export async function postQuery(req: QueryRequest): Promise<QueryResponse> {
  const { data } = await api.post('/query', req)
  return data
}

// ==================== v2.0 编辑 API ====================

// ----- 实体 CRUD -----

export async function createEntity(req: CreateEntityRequest): Promise<EntityResponse> {
  const { data } = await api.post('/editor/entities', req)
  return data
}

export async function getEntity(elementId: string): Promise<EntityResponse> {
  const { data } = await api.get(`/editor/entities/${encodeURIComponent(elementId)}`)
  return data
}

export async function updateEntity(
  elementId: string,
  req: UpdateEntityRequest,
): Promise<EntityResponse> {
  const { data } = await api.put(`/editor/entities/${encodeURIComponent(elementId)}`, req)
  return data
}

export async function deleteEntity(elementId: string): Promise<void> {
  await api.delete(`/editor/entities/${encodeURIComponent(elementId)}`)
}

export async function checkEntityDeletion(elementId: string): Promise<import('@/types').DeletionCheckResult> {
  const { data } = await api.get(`/editor/entities/${encodeURIComponent(elementId)}/deletion-check`)
  return data
}

// ----- 属性操作 -----

export async function setProperties(
  elementId: string,
  properties: Record<string, unknown>,
): Promise<EntityResponse> {
  const { data } = await api.post(
    `/editor/entities/${encodeURIComponent(elementId)}/properties`,
    { properties },
  )
  return data
}

export async function deleteProperty(
  elementId: string,
  key: string,
): Promise<EntityResponse> {
  const { data } = await api.delete(
    `/editor/entities/${encodeURIComponent(elementId)}/properties/${encodeURIComponent(key)}`,
  )
  return data
}

// ----- 关系 CRUD -----

export async function createRelationship(
  req: CreateRelationshipRequest,
): Promise<RelationshipResponse> {
  const { data } = await api.post('/editor/relationships', req)
  return data
}

export async function updateRelationship(
  relId: string,
  req: UpdateRelationshipRequest,
): Promise<RelationshipResponse> {
  const { data } = await api.put(`/editor/relationships/${encodeURIComponent(relId)}`, req)
  return data
}

export async function deleteRelationship(relId: string): Promise<void> {
  await api.delete(`/editor/relationships/${encodeURIComponent(relId)}`)
}

export async function fetchRelationship(relId: string): Promise<RelationshipResponse> {
  const { data } = await api.get(`/editor/relationships/${encodeURIComponent(relId)}`)
  return data
}

export async function updateRelationshipFull(
  relId: string,
  req: UpdateRelationshipRequest,
): Promise<RelationshipResponse> {
  const { data } = await api.put(`/editor/relationships/${encodeURIComponent(relId)}`, req)
  return data
}

// ----- 元数据 -----

export async function fetchAvailableLabels(): Promise<AvailableLabelsResponse> {
  const { data } = await api.get('/editor/labels')
  return data
}

export async function fetchAvailableRelationshipTypes(): Promise<AvailableRelationshipsResponse> {
  const { data } = await api.get('/editor/relationship-types')
  return data
}

export async function searchNodes(keyword: string): Promise<NodeSearchResult[]> {
  const { data } = await api.get('/editor/nodes/search', { params: { keyword } })
  return data
}

// ----- 关系实例列表 -----

export async function fetchRelationshipInstances(
  type: string,
): Promise<RelationshipInstanceSummary[]> {
  const { data } = await api.get('/editor/relationship-instances', { params: { type } })
  return data
}
