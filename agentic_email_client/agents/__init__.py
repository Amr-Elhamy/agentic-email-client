"""
Role-Based Email Agents

Specialized AI agents for email communication workflows.
"""

from .base import BaseEmailAgent, AgentRole, AgentAction, AgentDecision
from .sales_agent import SalesAgent
from .support_agent import SupportAgent
from .operations_agent import OperationsAgent

__all__ = [
    "BaseEmailAgent",
    "SalesAgent",
    "SupportAgent",
    "OperationsAgent",
    "AgentRole",
    "AgentAction",
    "AgentDecision",
]