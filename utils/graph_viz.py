import os
from typing import Optional

try:
    import networkx as nx  # type: ignore
    HAS_NX = True
except Exception:
    nx = None  # type: ignore
    HAS_NX = False


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


class AgentGraph:
    def __init__(self, base_dir: str = "memory") -> None:
        self.base_dir = base_dir
        if HAS_NX:
            self.G = nx.DiGraph()
        else:
            self.G = None
        ensure_dir(os.path.join(self.base_dir, "graphs"))

    def add_interaction(self, caller: str, callee: str, why: str) -> None:
        if HAS_NX and self.G is not None:
            self.G.add_node(caller)
            self.G.add_node(callee)
            self.G.add_edge(caller, callee, why=why)
        # If networkx is unavailable, silently skip but keep code paths working

    def save(self, session_id: Optional[str]) -> Optional[str]:
        if not session_id or not HAS_NX or self.G is None:
            return None
        graphs_dir = os.path.join(self.base_dir, "graphs")
        ensure_dir(graphs_dir)
        path = os.path.join(graphs_dir, f"{session_id}.graphml")
        nx.write_graphml(self.G, path)  # type: ignore
        return path
