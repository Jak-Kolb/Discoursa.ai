from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from .db import Base
import uuid
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)  # Twitter ID (e.g., "12345678")
    handle = Column(String)
    encrypted_api_key = Column(String)     # Fernet encrypted
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to debates started via Web App
    web_sessions = relationship("DebateSession", back_populates="user")

class DebateRoot(Base):
    """Represents a Tweet that triggered a debate."""
    __tablename__ = "debate_roots"
    id = Column(String, primary_key=True)  # The Tweet ID of the prompt
    topic = Column(String)                 # The text of the OP tweet
    op_handle = Column(String)             # The handle of the person being debated
    
    branches = relationship("DebateBranch", back_populates="root")

class DebateBranch(Base):
    """Represents a specific conversation thread under a root."""
    __tablename__ = "debate_branches"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    root_id = Column(String, ForeignKey("debate_roots.id"))
    challenger_id = Column(String, ForeignKey("users.id")) # The human debating
    last_tweet_id = Column(String) # Track the last tweet to reply to
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Store history as [{"role": "user", "content": "..."}, ...]
    history = Column(JSONB, default=list) 
    
    root = relationship("DebateRoot", back_populates="branches")

class BotState(Base):
    """Replaces Redis for tracking polling state."""
    __tablename__ = "bot_state"
    key = Column(String, primary_key=True) # e.g., "since_id"
    value = Column(String)
