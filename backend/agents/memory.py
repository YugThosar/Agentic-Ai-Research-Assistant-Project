"""
Memory Agent:
Manages three memory types:
  - Episodic:  Past conversations and interaction history
  - Semantic:  User interests, topic frequencies, persistent knowledge
  - Working:   Temporary per-session state (cleared at session end)

The Memory Agent:
  1. Loads relevant episodic context before reasoning
  2. Updates semantic memory based on queries
  3. Persists conversations after completion
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.agents.base import BaseAgent, AgentState
from backend.database import MemoryDB, ConversationDB, MessageDB, CitationDB

logger = logging.getLogger("apks.agent.memory")


class MemoryAgent(BaseAgent):
    name = "MemoryAgent"

    # ------------------------------------------------------------------ #
    # Load phase: called BEFORE reasoning                                  #
    # ------------------------------------------------------------------ #
    def load_context(self, state: AgentState) -> AgentState:
        """Load relevant episodic and semantic memory into state."""
        db: Session = state.get("db_session")
        conversation_id = state.get("conversation_id")

        # Load recent conversation messages for context
        if conversation_id and db:
            conv = db.query(ConversationDB).filter(ConversationDB.id == conversation_id).first()
            if conv:
                recent_msgs = sorted(conv.messages, key=lambda m: m.created_at)[-10:]
                state["conversation_history"] = [
                    {"role": m.role, "content": m.content} for m in recent_msgs
                ]

        # Load semantic memories for personalisation
        if db:
            semantic_memories = db.query(MemoryDB).filter(MemoryDB.category == "semantic").all()
            state["semantic_memory"] = {m.key: m.value for m in semantic_memories}

        return state

    # ------------------------------------------------------------------ #
    # Save phase: called AFTER reasoning                                   #
    # ------------------------------------------------------------------ #
    def execute(self, state: AgentState) -> AgentState:
        """Persist the completed conversation turn and update semantic memory."""
        db: Session = state.get("db_session")
        if not db:
            logger.error("MemoryAgent: No database session in state.")
            return state

        conversation_id = state.get("conversation_id")
        query = state.get("query", "")
        reasoning = state.get("reasoning", {})
        critique = state.get("critique", {})

        # Create or get conversation
        if not conversation_id:
            conv = ConversationDB(title=query[:60] + ("..." if len(query) > 60 else ""))
            db.add(conv)
            db.commit()
            db.refresh(conv)
            conversation_id = conv.id
            state["conversation_id"] = conversation_id
        else:
            conv = db.query(ConversationDB).filter(ConversationDB.id == conversation_id).first()
            if not conv:
                conv = ConversationDB(id=conversation_id, title=query[:60])
                db.add(conv)
                db.commit()

        # Save user message
        user_msg = MessageDB(
            conversation_id=conversation_id,
            role="user",
            content=query,
        )
        db.add(user_msg)

        # Save assistant message with full metadata
        assistant_content = reasoning.get("draft_answer", "")
        assistant_msg = MessageDB(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_content,
            confidence_score=critique.get("confidence"),
            planning_summary=json.dumps(state.get("plan", {})),
            reasoning_steps=reasoning.get("reasoning_steps", ""),
            critique_summary=json.dumps(critique),
            refinement_loops=state.get("refinement_loops", 0),
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)

        # Save citations
        retrieved_chunks = state.get("retrieved_chunks", [])
        evidence_used = set(reasoning.get("evidence_used", []))
        for chunk in retrieved_chunks:
            if not evidence_used or chunk.get("id") in evidence_used:
                citation = CitationDB(
                    message_id=assistant_msg.id,
                    chunk_id=chunk["id"],
                    source_doc=chunk.get("metadata", {}).get("source", "Unknown"),
                    page_number=chunk.get("metadata", {}).get("page_number", 1),
                )
                db.add(citation)

        # Update semantic memory: topic frequency tracking
        self._update_semantic_memory(db, query, state.get("plan", {}))
        db.commit()

        state["saved_message_id"] = assistant_msg.id
        logger.info(f"MemoryAgent saved turn to conversation {conversation_id}. Message ID: {assistant_msg.id}")
        return state

    def _update_semantic_memory(self, db: Session, query: str, plan: Dict):
        """Track user topic interests in semantic memory."""
        try:
            query_type = plan.get("query_type", "factual")
            required_sources = plan.get("required_sources", [])

            for topic in required_sources[:3]:  # limit topics per query
                existing = db.query(MemoryDB).filter(
                    MemoryDB.category == "semantic",
                    MemoryDB.key == f"topic:{topic}"
                ).first()
                if existing:
                    count = int(existing.value) + 1
                    existing.value = str(count)
                    existing.updated_at = datetime.utcnow()
                else:
                    db.add(MemoryDB(
                        category="semantic",
                        key=f"topic:{topic}",
                        value="1",
                    ))

            # Track query type frequency
            qt_key = f"query_type:{query_type}"
            existing_qt = db.query(MemoryDB).filter(
                MemoryDB.category == "semantic",
                MemoryDB.key == qt_key
            ).first()
            if existing_qt:
                existing_qt.value = str(int(existing_qt.value) + 1)
            else:
                db.add(MemoryDB(category="semantic", key=qt_key, value="1"))

        except Exception as e:
            logger.error(f"Failed to update semantic memory: {e}")
