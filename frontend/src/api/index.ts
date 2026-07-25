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
  SystemInfo,
  DBConnection,
  DBTableInfo,
  TableMapping,
  RelationshipMapping,
  ImportPreviewData,
  ImportResult,
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// ===== 本体浏览 =====

export async function fetchOntologyTree(systemId = 'disease_ontology'): Promise<OntologyTree> {
  const { data } = await api.get<OntologyTreeApiResponse>('/ontology/tree', {
    params: { system_id: systemId },
  })

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

export async function fetchRelationshipCatalog(systemId = 'disease_ontology'): Promise<RelationshipCatalogItem[]> {
  const { data } = await api.get('/ontology/relationships', { params: { system_id: systemId } })
  return data
}

export async function fetchSearch(keyword: string, systemId = 'disease_ontology'): Promise<SearchResult> {
  const { data } = await api.get('/ontology/search', { params: { keyword, system_id: systemId } })
  return data
}

// ===== 树形懒加载 =====

export async function fetchSubclassChildren(
  elementId: string,
  systemId = 'disease_ontology',
): Promise<{
  element_id: string
  name: string
  labels: string[]
  child_count: number
}[]> {
  const { data } = await api.get(
    `/ontology/nodes/${encodeURIComponent(elementId)}/subclasses`,
    { params: { system_id: systemId } },
  )
  return data
}

// ===== 图谱 =====

export async function fetchGraphOverview(systemId = 'disease_ontology'): Promise<GraphData> {
  const { data } = await api.get('/graph/overview', { params: { system_id: systemId } })
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

export async function createEntity(req: CreateEntityRequest, systemId = 'disease_ontology'): Promise<EntityResponse> {
  const { data } = await api.post('/editor/entities', req, { params: { system_id: systemId } })
  return data
}

export async function getEntity(elementId: string): Promise<EntityResponse> {
  const { data } = await api.get(`/editor/entities/${encodeURIComponent(elementId)}`)
  return data
}

export async function updateEntity(
  elementId: string,
  req: UpdateEntityRequest,
  systemId = 'disease_ontology',
): Promise<EntityResponse> {
  const { data } = await api.put(
    `/editor/entities/${encodeURIComponent(elementId)}`, req,
    { params: { system_id: systemId } },
  )
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
  systemId = 'disease_ontology',
): Promise<RelationshipResponse> {
  const { data } = await api.post('/editor/relationships', req, { params: { system_id: systemId } })
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

export async function fetchAvailableLabels(systemId = 'disease_ontology'): Promise<AvailableLabelsResponse> {
  const { data } = await api.get('/editor/labels', { params: { system_id: systemId } })
  return data
}

export async function fetchAvailableRelationshipTypes(systemId = 'disease_ontology'): Promise<AvailableRelationshipsResponse> {
  const { data } = await api.get('/editor/relationship-types', { params: { system_id: systemId } })
  return data
}

export async function searchNodes(keyword: string, systemId = 'disease_ontology'): Promise<NodeSearchResult[]> {
  const { data } = await api.get('/editor/nodes/search', { params: { keyword, system_id: systemId } })
  return data
}

// ----- 关系实例列表 -----

export async function fetchRelationshipInstances(
  type: string,
  systemId = 'disease_ontology',
): Promise<RelationshipInstanceSummary[]> {
  const { data } = await api.get('/editor/relationship-instances', { params: { type, system_id: systemId } })
  return data
}

// ==================== v3.0 系统管理 API ====================

export async function fetchSystemList(): Promise<SystemInfo[]> {
  const { data } = await api.get('/system/list')
  return data
}

export async function fetchDefaultSystem(): Promise<SystemInfo> {
  const { data } = await api.get('/system/default')
  return data
}

export async function deleteSystem(systemId: string): Promise<void> {
  await api.delete(`/system/${encodeURIComponent(systemId)}`, {
    params: { clean_neo4j: true },
  })
}

// ==================== v3.0 数据导入 API ====================

export async function previewExcel(file: File): Promise<ImportPreviewData> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post('/import/excel/preview', formData)
  return data
}

export async function importFromExcel(
  file: File,
  systemName: string,
  description: string,
): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('system_name', systemName)
  formData.append('description', description)
  const { data } = await api.post('/import/excel/import', formData)
  return data
}

export async function testDBConnection(conn: DBConnection): Promise<{ success: boolean; message: string }> {
  const { data } = await api.post('/import/db/test', conn)
  return data
}

export async function getDBTables(conn: DBConnection): Promise<DBTableInfo[]> {
  const { data } = await api.post('/import/db/tables', conn)
  return data
}

export async function previewDBImport(
  conn: DBConnection,
  entityMappings: TableMapping[],
  relationshipMappings?: RelationshipMapping[],
): Promise<ImportPreviewData> {
  const { data } = await api.post('/import/db/preview', {
    conn,
    entity_mappings: entityMappings,
    relationship_mappings: relationshipMappings,
  })
  return data
}

export async function importFromDB(
  conn: DBConnection,
  entityMappings: TableMapping[],
  systemName: string,
  description: string,
  relationshipMappings?: RelationshipMapping[],
): Promise<ImportResult> {
  const { data } = await api.post('/import/db/import', {
    conn,
    entity_mappings: entityMappings,
    relationship_mappings: relationshipMappings,
    system_name: systemName,
    description,
  })
  return data
}

export async function downloadTemplate(): Promise<Blob> {
  const response = await api.get('/import/template', { responseType: 'blob' })
  return response.data
}
