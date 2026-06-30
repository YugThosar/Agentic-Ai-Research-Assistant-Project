"""
Refinement Agent:
- Activates when confidence < threshold
- Identifies what's missing from the critique
- Requests focused additional retrieval on missing topics
- Re-runs reasoning with augmented evidence
- Tracks the number of refinement loops performed
"""
import logging
from typing import List, Dict, Any
from backend.agents.base import BaseAgent, AgentState
from backend.agents.retriever import RetrieverAgent
from backend.agents.reasoning import ReasoningAgent
from backend.agents.critic import CriticAgent
from backend.config import settings

logger = logging.getLogger("apks.agent.refiner")


class RefinementAgent(BaseAgent):
    name = "RefinementAgent"

    def __init__(self):
        self.retriever = RetrieverAgent()
        self.reasoner = ReasoningAgent()
        self.critic = CriticAgent()

    def execute(self, state: AgentState) -> AgentState:
        max_loops = settings.MAX_REFINEMENT_LOOPS
        threshold = settings.CONFIDENCE_THRESHOLD
        loop_count = 0

        while loop_count < max_loops:
            critique = state.get("critique", {})
            confidence = critique.get("confidence", 1.0)

            if confidence >= threshold:
                logger.info(f"Confidence {confidence:.2f} >= threshold {threshold}. Stopping refinement.")
                break

            loop_count += 1
            logger.info(f"Refinement loop {loop_count}/{max_loops}. Current confidence: {confidence:.2f}")

            # Build targeted additional queries from missing context and issues
            missing_context = critique.get("missing_context", [])
            issues = critique.get("issues", [])
            original_query = state.get("query", "")

            supplemental_queries = [original_query]  # always re-query with original
            for ctx in missing_context[:2]:
                supplemental_queries.append(ctx)

            # Retrieve additional evidence
            db_session = state.get("db_session")
            additional_chunks = self.retriever.retrieve(
                queries=supplemental_queries,
                db_session=db_session,
                top_k=settings.TOP_K,
            )

            # Merge with existing chunks (deduplicated)
            existing_ids = {c["id"] for c in state.get("retrieved_chunks", [])}
            new_chunks = [c for c in additional_chunks if c["id"] not in existing_ids]
            state["retrieved_chunks"] = state.get("retrieved_chunks", []) + new_chunks

            if new_chunks:
                logger.info(f"Refinement retrieved {len(new_chunks)} additional chunks.")
            else:
                logger.info("No new chunks found. Attempting to improve answer with existing evidence.")

            # Add refinement context to state for the reasoner
            state["refinement_hints"] = {
                "loop": loop_count,
                "issues": issues,
                "missing_context": missing_context,
                "previous_confidence": confidence,
            }

            # Re-run reasoning and critique
            state = self.reasoner.execute(state)
            state = self.critic.execute(state)

        state["refinement_loops"] = loop_count
        logger.info(f"Refinement complete. Loops: {loop_count}, Final confidence: {state.get('critique', {}).get('confidence', 0):.2f}")
        return state
