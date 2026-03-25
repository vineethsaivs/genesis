"""Pydantic models for API request/response schemas."""

from pydantic import BaseModel, Field

# --- Health ---


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str


# --- Skills ---


class SkillResponse(BaseModel):
    """Single skill detail."""

    id: str
    name: str
    description: str
    category: str
    parent_id: str | None = None
    is_core: bool = False
    code_path: str = ""
    created_at: str = ""
    use_count: int = 0
    status: str = "active"


class SkillListResponse(BaseModel):
    """List of skills."""

    skills: list[SkillResponse]
    total: int


# --- Skill Tree (react-force-graph-2d format) ---


class SkillTreeNode(BaseModel):
    """Node for force-graph visualization."""

    id: str
    name: str
    category: str
    is_core: bool = False
    val: int = Field(default=1, description="Node size for force-graph")


class SkillTreeLink(BaseModel):
    """Edge for force-graph visualization."""

    source: str
    target: str


class SkillTreeResponse(BaseModel):
    """Complete skill tree for the frontend."""

    nodes: list[SkillTreeNode]
    links: list[SkillTreeLink]


# --- Evolution History ---


class EvolutionRecord(BaseModel):
    """Single evolution event."""

    id: str
    skill_id: str
    skill_name: str
    trigger_task: str
    code_snippet: str = ""
    test_passed: bool = False
    created_at: str = ""


class EvolutionHistoryResponse(BaseModel):
    """List of evolution events."""

    records: list[EvolutionRecord]
    total: int


# --- Task ---


class TaskRequest(BaseModel):
    """Incoming task from the user."""

    task: str


class TaskResponse(BaseModel):
    """Acknowledgement after accepting a task."""

    task_id: str
    status: str = "accepted"
    message: str = "Connect to /ws/agent for streaming updates"


# --- Events & Errors ---


class AgentEvent(BaseModel):
    """Single event emitted over WebSocket."""

    type: str
    data: dict | None = None
    message: str = ""


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    error: str
    detail: str = ""
