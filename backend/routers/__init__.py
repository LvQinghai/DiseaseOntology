from .ontology_router import router as ontology_router
from .graph_router import router as graph_router
from .query_router import router as query_router
from .editor_router import router as editor_router
from .system_router import router as system_router
from .import_router import router as import_router

__all__ = [
    "ontology_router",
    "graph_router",
    "query_router",
    "editor_router",
    "system_router",
    "import_router",
]
