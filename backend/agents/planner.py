"""
Planner Agent:
- Classifies query type (factual, comparative, summarization, research, decision, multi-hop)
- Decomposes complex queries into subqueries
- Produces an execution plan for the orchestrator
"""
import json
import logging
from backend.agents.base import BaseAgent, AgentState
from backend.utils.llm import llm_generate

logger = logging.getLogger("apks.agent.planner")

SYSTEM_PROMPT = """You are an expert query planner for a Personal Knowledge System.
Analyze the user's query and produce a structured execution plan.

Return ONLY valid JSON in this exact schema:
{
  "query_type": "<factual|comparative|summarization|research|decision|multi_hop>",
  "complexity": "<simple|moderate|complex>",
  "subqueries": ["<subquery_1>", "<subquery_2>"],
  "required_sources": ["<topic or keyword to look for>"],
  "reasoning_notes": "<brief explanation of your plan>"
}

Rules:
- For simple factual queries, subqueries can just contain the original query.
- For multi-hop or comparative queries, break them into 2-4 targeted subqueries.
- required_sources should contain keywords/topic areas that help guide retrieval.
"""


class PlannerAgent(BaseAgent):
    name = "PlannerAgent"

    def execute(self, state: AgentState) -> AgentState:
        query = state.get("query", "")
        conversation_history = state.get("conversation_history", [])

        # Build context-aware prompt
        history_text = ""
        if conversation_history:
            recent = conversation_history[-4:]  # last 2 turns
            history_text = "\n".join(
                f"{m['role'].upper()}: {m['content'][:300]}" for m in recent
            )
            history_text = f"\n\nRecent conversation context:\n{history_text}\n"

        prompt = f"""User Query: "{query}"{history_text}
        
Produce a structured execution plan for this query."""

        try:
            raw = llm_generate(
                prompt=prompt,
                system_instruction=SYSTEM_PROMPT,
                json_mode=True,
                provider=state.get("model_provider"),
                model_name=state.get("model_name"),
            )
            plan = json.loads(raw)
        except Exception as e:
            logger.error(f"PlannerAgent failed: {e}")
            plan = {
                "query_type": "factual",
                "complexity": "simple",
                "subqueries": [query],
                "required_sources": [],
                "reasoning_notes": "Fallback plan due to planning error.",
            }

        state["plan"] = plan
        logger.info(f"PlannerAgent produced plan: type={plan.get('query_type')}, subqueries={len(plan.get('subqueries', []))}")
        return state
