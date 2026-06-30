"""
Reasoning Agent:
- Analyzes retrieved evidence from multiple documents
- Performs chain-of-thought reasoning
- Synthesizes information across sources
- Identifies conflicting claims
- Produces a draft answer with inline citations
"""
import json
import logging
from typing import List, Dict, Any
from backend.agents.base import BaseAgent, AgentState
from backend.utils.llm import llm_generate

logger = logging.getLogger("apks.agent.reasoner")

SYSTEM_PROMPT = """You are a rigorous research analyst and expert reasoner for a Personal Knowledge System.

You are given a user query and retrieved evidence chunks from their personal documents.

Your task:
1. Carefully read each evidence chunk and note its source document and page.
2. Synthesize information across multiple sources using chain-of-thought reasoning.
3. Identify any conflicting claims between sources and flag them.
4. Generate a comprehensive, well-structured answer grounded entirely in the evidence.
5. For every factual claim, cite the source document like: [Source: filename.pdf, Page X].

Guidelines:
- If evidence is insufficient, say so explicitly — do NOT hallucinate.
- Structure your answer with clear paragraphs.
- Show your reasoning process briefly before the final answer.
- Ensure every major claim has at least one citation.

Return your response in this JSON format:
{
  "reasoning_steps": "<step-by-step chain of thought>",
  "draft_answer": "<final structured answer with inline citations>",
  "conflicts_detected": ["<conflict description if any>"],
  "evidence_used": ["<chunk_id_1>", "<chunk_id_2>"]
}
"""


class ReasoningAgent(BaseAgent):
    name = "ReasoningAgent"

    def execute(self, state: AgentState) -> AgentState:
        query = state.get("query", "")
        retrieved_chunks = state.get("retrieved_chunks", [])
        plan = state.get("plan", {})

        if not retrieved_chunks:
            state["reasoning"] = {
                "reasoning_steps": "No evidence was retrieved.",
                "draft_answer": "I could not find relevant information in your documents to answer this question. Please upload documents covering this topic.",
                "conflicts_detected": [],
                "evidence_used": [],
            }
            return state

        # Format evidence for the prompt
        evidence_text = ""
        for i, chunk in enumerate(retrieved_chunks):
            source = chunk.get("metadata", {}).get("source", "Unknown")
            page = chunk.get("metadata", {}).get("page_number", chunk.get("page_number", 1))
            chunk_id = chunk.get("id", f"chunk_{i}")
            evidence_text += f"\n---\n[Chunk ID: {chunk_id}] [Source: {source}, Page {page}]\n{chunk['content']}\n"

        prompt = f"""User Query: "{query}"

Query Type: {plan.get('query_type', 'factual')}
Reasoning Notes from Planner: {plan.get('reasoning_notes', '')}

Retrieved Evidence:
{evidence_text}

Now perform chain-of-thought reasoning and produce a comprehensive answer with citations."""

        try:
            raw = llm_generate(
                prompt=prompt,
                system_instruction=SYSTEM_PROMPT,
                json_mode=True,
                provider=state.get("model_provider"),
                model_name=state.get("model_name"),
            )
            reasoning = json.loads(raw)
        except Exception as e:
            logger.error(f"ReasoningAgent failed: {e}")
            # Fallback: generate a plain text answer without JSON mode
            try:
                plain_answer = llm_generate(
                    prompt=f"Answer this question based on the evidence:\nQuery: {query}\nEvidence: {evidence_text[:3000]}",
                    provider=state.get("model_provider"),
                    model_name=state.get("model_name"),
                )
                reasoning = {
                    "reasoning_steps": "Direct answer generation (JSON parsing failed).",
                    "draft_answer": plain_answer,
                    "conflicts_detected": [],
                    "evidence_used": [c.get("id", "") for c in retrieved_chunks],
                }
            except Exception as fe:
                reasoning = {
                    "reasoning_steps": "Reasoning failed completely.",
                    "draft_answer": "Unable to generate an answer due to an internal error.",
                    "conflicts_detected": [],
                    "evidence_used": [],
                }

        state["reasoning"] = reasoning
        logger.info(f"ReasoningAgent completed. Evidence used: {len(reasoning.get('evidence_used', []))}")
        return state
