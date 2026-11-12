"""
Sales-focused email agent for handling inquiries, proposals, and follow-ups.
"""

from typing import List, Dict, Any
from datetime import datetime

from .base import BaseEmailAgent, AgentRole, AgentAction, AgentDecision
from ..adapters import EmailMessage, EmailStatus


class SalesAgent(BaseEmailAgent):
    """Agent specialized for sales communication - leads, proposals, and follow-ups."""

    def __init__(self, adapter=None, memory=None):
        super().__init__(
            role=AgentRole.SALES,
            adapter=adapter,
            memory=memory,
            confidence_threshold=0.75,
            escalation_threshold=0.25,
        )

    @property
    def system_prompt(self) -> str:
        return """You are Alex, a professional sales representative for our company.
Your role is to:
- Respond promptly to sales inquiries and lead generation emails
- Send personalized follow-up emails to prospects
- Schedule demos and meetings
- Provide pricing information and answer product questions
- Qualify leads by gathering key information

Tone: Professional, enthusiastic, helpful, and consultative.
Always be helpful even when rejecting or declining requests.
Never disclose internal pricing until properly qualified."""

    @property
    def email_filters(self) -> List[str]:
        return [
            "lead",
            "quote",
            "pricing",
            "demo",
            "trial",
            "information",
            "sales",
            "buy",
            "purchase",
            "proposal",
            "cost",
            "estimate",
            "feature",
            "product",
            "capability",
        ]

    async def _make_decision(self, context: Dict[str, Any]) -> AgentDecision:
        """Make a sales-specific decision based on email content."""
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

        # Check for pricing requests
        pricing_triggers = ["pricing", "quote", "cost", "estimate", "price"]
        if any(t in body_lower or t in subject_lower for t in pricing_triggers):
            return AgentDecision(
                action=AgentAction.REPLY,
                confidence=0.9,
                reason="Pricing inquiry detected - customer requesting price information",
                reply_body="Thank you for your interest! I'd be happy to provide you with a custom quote. Could you share your estimated timeline and specific requirements so I can prepare the most accurate pricing for you?",
                reply_html_body="""
                <p>Thank you for your interest!</p>
                <p>I'd be happy to provide you with a custom quote. Could you share your estimated timeline and specific requirements so I can prepare the most accurate pricing for you?</p>
                <p>Looking forward to helping you get started!</p>
                """,
            )

        # Check for demo requests
        demo_triggers = ["demo", "example", "tour", "trial", "sample"]
        if any(t in body_lower or t in subject_lower for t in demo_triggers):
            return AgentDecision(
                action=AgentAction.REPLY,
                confidence=0.85,
                reason="Demo/trial request detected",
                reply_body="Great news! I'd love to show you our platform in action. I can schedule a personalized demo at your convenience. What days/times work best for you? I'll send over a calendar invitation.",
                reply_html_body="""
                <p>Great news! I'd love to show you our platform in action.</p>
                <p>I can schedule a personalized demo at your convenience. What days/times work best for you? I'll send over a calendar invitation.</p>
                """,
            )

        # Check for feature inquiries
        feature_triggers = ["feature", "capability", "function", "support", "integration"]
        if any(t in body_lower or t in subject_lower for t in feature_triggers):
            return AgentDecision(
                action=AgentAction.REPLY,
                confidence=0.8,
                reason="Feature inquiry detected",
                reply_body="I'd be happy to walk you through our features! Our platform offers several capabilities that might interest you. Let me connect you with our solution engineer who can provide detailed technical information. Would you prefer a brief call this week?",
            )

        # Check for lead qualification
        if "contact" in body_lower or "reach" in body_lower:
            return AgentDecision(
                action=AgentAction.REPLY,
                confidence=0.7,
                reason="General inquiry - qualify the lead",
                reply_body="Thanks for reaching out! I'm interested in learning more about your needs. Could you tell me a bit about your current situation and what you're looking to accomplish?",
            )

        # Default: escalate to human for complex inquiries
        return AgentDecision(
            action=AgentAction.ESCALATE,
            confidence=0.3,
            reason="Complex sales inquiry requiring human attention",
            should_escalate=True,
            escalation_reason="Complex inquiry outside automated handling scope",
        )