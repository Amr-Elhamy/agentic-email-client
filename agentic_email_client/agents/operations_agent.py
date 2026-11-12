"""
Operations-focused email agent for business operations and internal workflows.
"""

from typing import List, Dict, Any
from datetime import datetime

from .base import BaseEmailAgent, AgentRole, AgentAction, AgentDecision
from ..adapters import EmailMessage, EmailStatus


class OperationsAgent(BaseEmailAgent):
    """Agent specialized for operations - onboarding, logistics, internal processes."""

    def __init__(self, adapter=None, memory=None):
        super().__init__(
            role=AgentRole.OPERATIONS,
            adapter=adapter,
            memory=memory,
            confidence_threshold=0.7,
            escalation_threshold=0.3,
        )

    @property
    def system_prompt(self) -> str:
        return """You are Morgan, an operations coordinator.
Your role is to:
- Handle onboarding communications
- Coordinate logistics and scheduling
- Manage internal process requests
- Track deliverables and deadlines
- Organize meeting minutes and action items

Tone: Efficient, organized, detail-oriented, and professional.
Always confirm next steps and deadlines.
Provide clear timelines and expectations."""

    @property
    def email_filters(self) -> List[str]:
        return [
            "onboarding",
            "setup",
            "account",
            "team",
            "schedule",
            "meeting",
            "deadline",
            "deliverable",
            "process",
            "procedure",
            "workflow",
            "training",
            "orientation",
            "access",
            "permission",
            "role",
            "permissions",
            "calendar",
            "availability",
            "reminder",
            "follow up",
            "action item",
        ]

    async def _make_decision(self, context: Dict[str, Any]) -> AgentDecision:
        """Make an operations-specific decision based on email content."""
        email = context.get("email")
        if not email:
            return AgentDecision(
                action=AgentAction.ESCALATE,
                confidence=0.1,
                reason="No email content to analyze",
                should_escalate=True,
                escalation_reason="Missing email data",
            )

        body_lower = (email.body_plain or email.body_html or "").lower()
        subject_lower = email.subject.lower() if email.subject else ""

        # Check for onboarding requests
        onboarding_patterns = ["new hire", "onboarding", "new employee", "orientation", "start date"]
        if any(p in body_lower or p in subject_lower for p in onboarding_patterns):
            return AgentDecision(
                action=AgentAction.REPLY,
                confidence=0.85,
                reason="Onboarding request detected",
                reply_body="I'll help with your onboarding setup!\n\nFor new hire onboarding, I need:\n1. Employee name and start date\n2. Role/title\n3. Department\n4. Equipment needs (laptop, phone, etc.)\n5. Access requirements\n\nOnce I have these details, I'll:\n- Schedule orientation\n- Arrange equipment\n- Set up system access\n- Send welcome materials\n\nPlease reply with the requested information so we can get started.",
                labels=["onboarding", "new-hire"],
            )

        # Check for meeting scheduling
        meeting_patterns = ["meeting", "call", "schedule", "available", "time"]
        if any(p in body_lower or p in subject_lower for p in meeting_patterns):
            return AgentDecision(
                action=AgentAction.REPLY,
                confidence=0.8,
                reason="Meeting request detected",
                reply_body="I can help schedule your meeting! Please provide:\n\n1. Preferred days/times (include time zone)\n2. Meeting purpose\n3. Expected attendees\n4. Duration needed\n\nI'll then check availability and send a calendar invitation.\n\nFor urgent requests, please include 'URGENT' in your reply.",
                labels=["meeting", "scheduling"],
            )

        # Check for deadline/due date requests
        deadline_patterns = ["deadline", "due date", "complete by", "finish by", "deliverable"]
        if any(p in body_lower or p in subject_lower for p in deadline_patterns):
            return AgentDecision(
                action=AgentAction.REPLY,
                confidence=0.75,
                reason="Deadline tracking request detected",
                reply_body="I'll help track this deadline.\n\nPlease confirm:\n1. What needs to be delivered\n2. Due date\n3. Who it's for\n4. Any dependencies or blockers\n\nI'll create a tracking record and follow up as needed.",
                labels=["deadline", "tracking"],
            )

        # Check for access/permission requests
        access_patterns = ["access", "permission", "role", "account", "login", "credentials"]
        if any(p in body_lower or p in subject_lower for p in access_patterns):
            return AgentDecision(
                action=AgentAction.ARCHIVE,
                confidence=0.7,
                reason="Access request - route to IT/security team",
                labels=["access-request", "it-ticket"],
            )

        # Check for follow-up reminders
        if "follow up" in body_lower or "reminder" in body_lower:
            return AgentDecision(
                action=AgentAction.REPLY,
                confidence=0.85,
                reason="Follow-up reminder detected",
                reply_body="I'll add this to my tracking list.\n\nWhat is the follow-up regarding and when should I check back? I'll set a reminder to reach out if no response is received by the specified date.",
                labels=["follow-up", "reminder"],
            )

        # Check for action items
        action_patterns = ["action item", "next steps", "to do", "task", "todo"]
        if any(p in body_lower or p in subject_lower for p in action_patterns):
            return AgentDecision(
                action=AgentAction.LABEL,
                confidence=0.8,
                reason="Action item identified - needs follow-up",
                labels=["action-item", "needs-followup"],
            )

        # Default: archive for internal ops discussions
        return AgentDecision(
            action=AgentAction.ARCHIVE,
            confidence=0.6,
            reason="Operations discussion - file for reference",
            labels=["operations"],
        )