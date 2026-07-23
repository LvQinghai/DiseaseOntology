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
  return {
    name: props.name || (data.labels && data.labels[0]) || '',
    type: (data.labels && data.labels[0]) || '',
    properties: Object.entries(props).map(([key, value]) => ({ key, value })),
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
