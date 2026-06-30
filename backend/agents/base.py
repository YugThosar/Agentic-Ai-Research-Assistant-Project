"""
Base Agent: shared state container and abstract execute method.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict


class AgentState(dict):
    """Mutable state dict passed through the agent pipeline."""
    pass


class BaseAgent(ABC):
    name: str = "BaseAgent"

    @abstractmethod
    def execute(self, state: AgentState) -> AgentState:
        """Execute agent logic and return updated state."""
        ...
