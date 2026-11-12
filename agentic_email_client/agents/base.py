"""
Base agent class for email workflow automation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime
from enum import Enum
import asyncio
import json

from ..adapters import EmailAdapter, EmailMessage, EmailStatus
from ..memory import VectorMemory


class AgentRole(Enum):
    SALES = "sales"
    SUPPORT = "support"
    OPERATIONS = "operations"


class AgentAction(Enum):
    READ = "read_email"
    REPLY = "reply_email"
    SEND = "send_email"
    FORWARD = "forward_email"
    ARCHIVE = "archive_email"
    DELETE = "delete_email"
    LABEL = "label_email"
    ESCALATE = "escalate_to_human"
    REMIND = "remind_user"


@dataclass
class AgentDecision:
    """Represents an agent's decision about an email."""
    action: AgentAction
    confidence: float
    reason: str
    reply_body: Optional[str] = None
    reply_html_body: Optional[str] = None
    labels: List[str] = None
    forward_to: Optional[str] = None
    should_escalate: bool = False
    escalation_reason: Optional[str] = None


class BaseEmailAgent(ABC):
    """Base class for role-based email agents with LangGraph integration."""

    def __init__(
        self,
        role: AgentRole,
        adapter: EmailAdapter,
        memory: VectorMemory = None,
        confidence_threshold: float = 0.7,
        escalation_threshold: float = 0.3,
    ):
        self.role = role
        self.adapter = adapter
        self.memory = memory or VectorMemory()
        self.confidence_threshold = confidence_threshold
        self.escalation_threshold = escalation_threshold
        self._running = False

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt for this agent role."""
        pass

    @property
    @abstractmethod
    def email_filters(self) -> List[str]:
        """Return email subject/content patterns this agent should handle."""
        pass

    async def is_eligible_for_email(self, email: EmailMessage) -> bool:
        """Check if this agent should handle the given email based on role-specific rules."""
        # Check unread status
        if email.status == EmailStatus.UNREAD:
            return True

        # Check role-specific filters
        for pattern in self.email_filters:
            if pattern.lower() in email.subject.lower() or pattern.lower() in (email.body_plain or "").lower():
                return True

        return False

    async def analyze_email(self, email: EmailMessage) -> AgentDecision:
        """Analyze an email and determine the appropriate action."""
        # Retrieve relevant context from memory
        context = await self.memory.search(
            query=email.subject or email.body_plain or "",
            limit=5,
        )

        # Build analysis context
        analysis_context = {
            "email": email,
            "role": self.role.value,
            "history": context,
            "timestamp": datetime.now().isoformat(),
        }

        # This is where LangGraph would be integrated for more complex reasoning
        # For the simple prototype, we use basic rule-based analysis
        decision = await self._make_decision(analysis_context)

        # Store decision in memory for learning
        if self.memory:
            await self.memory.store(
                query=f"email_analysis_{email.id}",
                metadata=analysis_context,
                embedding=decision.action.value,
            )

        return decision

    async def _make_decision(self, context: Dict[str, Any]) -> AgentDecision:
        """Make a decision based on email content. Override for role-specific logic."""
        raise NotImplementedError("Subclasses must implement _make_decision")

    async def process_email(self, email: EmailMessage) -> AgentDecision:
        """Main entry point for processing an email."""
        # Verify eligibility
        if not await self.is_eligible_for_email(email):
            return AgentDecision(
                action=AgentAction.READ,
                confidence=0.5,
                reason="Email not eligible for this agent's role",
            )

        # Analyze and decide
        return await self.analyze_email(email)

    async def execute_action(self, email: EmailMessage, decision: AgentDecision) -> bool:
        """Execute the agent's decision on an email."""
        try:
            if decision.action == AgentAction.REPLY:
                await self.adapter.reply_to_message(
                    message_id=email.id,
                    body=decision.reply_body or "",
                    html_body=decision.reply_html_body,
                )
            elif decision.action == AgentAction.ARCHIVE:
                await self.adapter.archive_message(email.id)
            elif decision.action == AgentAction.DELETE:
                await self.adapter.delete_message(email.id)
            elif decision.action == AgentAction.LABEL:
                await self.adapter.label_message(email.id, decision.labels or [])

            # If no escalation needed
            return not decision.should_escalate

        except Exception as e:
            print(f"Error executing action {decision.action.value}: {e}")
            return False

    async def process_and_respond(self, email: EmailMessage) -> Dict[str, Any]:
        """Process an email: analyze, decide, execute, and return results."""
        decision = await self.process_email(email)
        success = await self.execute_action(email, decision)

        return {
            "email_id": email.id,
            "action": decision.action.value,
            "confidence": decision.confidence,
            "success": success,
            "escalated": decision.should_escalate,
            "timestamp": datetime.now().isoformat(),
        }

    async def run(self, interval_seconds: int = 10) -> None:
        """Run the agent continuously processing new emails."""
        self._running = True

        while self._running:
            try:
                # Fetch unread emails
                messages = await self.adapter.get_messages(
                    max_results=20,
                    status=EmailStatus.UNREAD,
                )

                # Process each message
                for email in messages:
                    await self.process_and_respond(email)

                # Wait before next iteration
                await asyncio.sleep(interval_seconds)

            except Exception as e:
                print(f"Agent run error: {e}")
                await asyncio.sleep(30)

    def stop(self) -> None:
        """Stop the agent's processing loop."""
        self._running = False

    async def close(self) -> None:
        """Clean up resources."""
        self.stop()
        if self.adapter:
            await self.adapter.close()