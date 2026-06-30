from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- Document Schemas ---
class DocumentBase(BaseModel):
    filename: str
    file_type: str
    file_size: int

class DocumentResponse(DocumentBase):
    id: str
    upload_date: datetime
    status: str
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

# --- Chunk Schemas ---
class ChunkResponse(BaseModel):
    id: str
    doc_id: str
    chunk_index: int
    content: str
    page_number: int

    class Config:
        from_attributes = True

# --- Citation Schemas ---
class CitationResponse(BaseModel):
    id: str
    message_id: str
    chunk_id: str
    source_doc: str
    page_number: int
    content: Optional[str] = None

    class Config:
        from_attributes = True

# --- Evaluation Schemas ---
class EvaluationBase(BaseModel):
    faithfulness: Optional[float] = None
    groundedness: Optional[float] = None
    relevance: Optional[float] = None
    planning_accuracy: Optional[float] = None
    critique_accuracy: Optional[float] = None
    feedback: Optional[str] = None

class EvaluationResponse(EvaluationBase):
    id: str
    message_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class FeedbackRequest(BaseModel):
    message_id: str
    feedback: str  # "thumbs_up" or "thumbs_down"

# --- Message & Conversation Schemas ---
class MessageBase(BaseModel):
    role: str
    content: str

class MessageResponse(MessageBase):
    id: str
    conversation_id: str
    created_at: datetime
    confidence_score: Optional[float] = None
    planning_summary: Optional[str] = None
    reasoning_steps: Optional[str] = None
    critique_summary: Optional[str] = None
    refinement_loops: int
    citations: List[CitationResponse] = []
    evaluations: List[EvaluationResponse] = []

    class Config:
        from_attributes = True

class ConversationBase(BaseModel):
    title: str

class ConversationResponse(ConversationBase):
    id: str
    created_at: datetime
    messages: List[MessageResponse] = []

    class Config:
        from_attributes = True

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    query: str
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    stream: bool = True

# --- Memory Schemas ---
class MemoryBase(BaseModel):
    category: str
    key: str
    value: str

class MemoryResponse(MemoryBase):
    id: str
    updated_at: datetime

    class Config:
        from_attributes = True

class MemoryUpdateRequest(BaseModel):
    category: str
    key: str
    value: str

# --- Knowledge Graph Schemas ---
class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # "Document", "Entity", "Concept"
    properties: Dict[str, Any] = {}

class GraphEdge(BaseModel):
    source: str
    target: str
    label: str  # "cites", "mentions", "related_to", etc.
    properties: Dict[str, Any] = {}

class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
