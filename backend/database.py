from datetime import datetime
import uuid
from sqlalchemy import create_engine, Column, String, Integer, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from backend.config import settings

# Determine DB URL based on STORAGE_MODE
if settings.STORAGE_MODE == "production":
    db_url = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
else:
    db_url = settings.DATABASE_URL

# Handle SQLite specifically (need check_same_thread configuration)
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(db_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper function to generate string UUIDs
def generate_uuid():
    return str(uuid.uuid4())

class DocumentDB(Base):
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="processing")  # processing, completed, error
    error_message = Column(Text, nullable=True)
    
    chunks = relationship("ChunkDB", back_populates="document", cascade="all, delete-orphan")

class ChunkDB(Base):
    __tablename__ = "chunks"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    doc_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    page_number = Column(Integer, default=1)
    
    document = relationship("DocumentDB", back_populates="chunks")
    citations = relationship("CitationDB", back_populates="chunk", cascade="all, delete-orphan")

class ConversationDB(Base):
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, default="New Conversation")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    messages = relationship("MessageDB", back_populates="conversation", cascade="all, delete-orphan")

class MessageDB(Base):
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Agent metadata
    confidence_score = Column(Float, nullable=True)
    planning_summary = Column(Text, nullable=True)  # JSON representation of plan
    reasoning_steps = Column(Text, nullable=True)    # Chain of thought markdown
    critique_summary = Column(Text, nullable=True)   # JSON representation of issues
    refinement_loops = Column(Integer, default=0)
    
    conversation = relationship("ConversationDB", back_populates="messages")
    citations = relationship("CitationDB", back_populates="message", cascade="all, delete-orphan")
    evaluations = relationship("EvaluationDB", back_populates="message", cascade="all, delete-orphan")

class CitationDB(Base):
    __tablename__ = "citations"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    message_id = Column(String, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    chunk_id = Column(String, ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False)
    source_doc = Column(String, nullable=False)
    page_number = Column(Integer, default=1)
    
    message = relationship("MessageDB", back_populates="citations")
    chunk = relationship("ChunkDB", back_populates="citations")

class MemoryDB(Base):
    __tablename__ = "memory"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    category = Column(String, nullable=False)  # episodic, semantic, working
    key = Column(String, nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EvaluationDB(Base):
    __tablename__ = "evaluations"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    message_id = Column(String, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    faithfulness = Column(Float, nullable=True)
    groundedness = Column(Float, nullable=True)
    relevance = Column(Float, nullable=True)
    planning_accuracy = Column(Float, nullable=True)
    critique_accuracy = Column(Float, nullable=True)
    feedback = Column(String, nullable=True)  # thumbs_up, thumbs_down
    created_at = Column(DateTime, default=datetime.utcnow)
    
    message = relationship("MessageDB", back_populates="evaluations")

# Database initialization
def init_db():
    Base.metadata.create_all(bind=engine)
