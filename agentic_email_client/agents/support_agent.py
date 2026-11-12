"""
Support-focused email agent for handling customer inquiries and issues.
"""

from typing import List, Dict, Any
from datetime import datetime

from .base import BaseEmailAgent, AgentRole, AgentAction, AgentDecision
from ..adapters import EmailMessage, EmailStatus


class SupportAgent(BaseEmailAgent):
    """Agent specialized for customer support - issues, questions, and troubleshooting."""

    def __init__(self, adapter=None, memory=None):
        super().__init__(
            role=AgentRole.SUPPORT,
            adapter=adapter,
            memory=memory,
            confidence_threshold=0.8,
            escalation_threshold=0.2,
        )

    @property
    def system_prompt(self) -> str:
        return """You are Sam, a customer support specialist.
Your role is to:
- Quickly resolve customer issues and questions
- Provide troubleshooting guidance
- Explain features and usage
- Escalate complex technical issues appropriately
- Follow up to ensure satisfaction

Tone: Empathetic, patient, helpful, and professional.
Always acknowledge the customer's frustration when appropriate.
Provide clear, step-by-step instructions.
Never blame the customer."""

    @property
    def email_filters(self) -> List[str]:
        return [
            "help",
            "issue",
            "problem",
            "error",
            "bug",
            "trouble",
            "question",
            "support",
            "assistance",
            "can't",
            "unable",
            "doesn't work",
            "not working",
            "password",
            "account",
            "login",
            "sign in",
            "access",
            "reset",
            "not receiving",
            "notification",
            "setting",
            "configuration",
            "setup",
            "install",
        ]

    async def _make_decision(self, context: Dict[str, Any]) -> AgentDecision:
        """Make a support-specific decision based on email content."""
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

        # Check for urgent issues
        urgent_patterns = ["urgent", "asap", "emergency", "immediately"]
        is_urgent = any(p in body_lower or p in subject_lower for p in urgent_patterns)
        urgency_emoji = "🔴 URGENT: " if is_urgent else ""

        # Check for password/account issues
        password_patterns = ["password", "login", "account", "sign in", "reset"]
        if any(p in body_lower or p in subject_lower for p in password_patterns):
            return AgentDecision(
                action=AgentAction.REPLY,
                confidence=0.95,
                reason="Account/password issue detected",
                reply_body=f"{urgency_emoji}I can help you with your account access issue. Please try these steps:\n\n1. Go to our login page and click 'Forgot Password'\n2. Enter your email address to receive a reset link\n3. Follow the link and create a new password\n\nIf these steps don't resolve the issue, please reply with:\n- Your account email\n- The exact error message you're seeing\n\nI'll look into this right away!",
            )

        # Check for password reset confirmation
        if "reset" in body_lower and "link" in body_lower:
            return AgentDecision(
                action=AgentAction.REPLY,
                confidence=0.9,
                reason="Password reset confirmation - provide guidance",
                reply_body=f"{urgency_emoji}Thanks for resetting your password! If you didn't receive the email, check your spam/junk folder. If you need further assistance, let me know and I'll resend the reset instructions.",
            )

        # Check for technical issues
        tech_patterns = ["error", "bug", "crash", "not working", "doesn't work", "broken"]
        if any(p in body_lower or p in subject_lower for p in tech_patterns):
            return AgentDecision(
                action=AgentAction.ESCALATE,
                confidence=0.85,
                reason="Technical issue requiring engineering review",
                should_escalate=True,
                escalation_reason="Technical issue needs detailed investigation",
            )

        # Check for billing/questions
        billing_patterns = ["bill", "invoice", "charge", "payment", "billing"]
        if any(p in body_lower or p in subject_lower for p in billing_patterns):
            return AgentDecision(
                action=AgentAction.REPLY,
                confidence=0.75,
                reason="Billing inquiry - needs human review",
                should_escalate=True,
                escalation_reason="Billing details require human processing",
            )

        # Check for notification issues
        if "not receiving" in body_lower or "notification" in body_lower:
            return AgentDecision(
                action=AgentAction.REPLY,
                confidence=0.85,
                reason="Notification delivery issue",
                reply_body=f"{urgency_emoji}To help diagnose your notification issue:\n\n1. Check that notifications are enabled in your account settings\n2. Ensure email notifications are turned on\n3. Check your spam/junk folder\n4. Verify the email address on your account is correct\n\nIf the problem persists, reply with:\n- What type of notifications you're missing\n- Your account email\n\nThis will help me investigate further!",
            )

        # Check for account access issues
        access_patterns = ["access", "can't access", "locked", "blocked"]
        if any(p in body_lower or p in subject_lower for p in access_patterns):
            return AgentDecision(
                action=AgentAction.REPLY,
                confidence=0.9,
                reason="Account access issue",
                reply_body=f"{urgency_emoji}I can help restore your account access. Let me verify your account details first - could you please reply with:\n\n1. Your account email address\n2. Any error message you're seeing\n\nI'll process this immediately for you.",
            )

        # Default: helpful response for general questions
        return AgentDecision(
            action=AgentAction.REPLY,
            confidence=0.6,
            reason="General support question - provide helpful response",
            reply_body="I'd be happy to help! Could you provide a bit more detail about what you're experiencing? Specifically:\n\n1. What you're trying to do\n2. What's happening (or not happening)\n3. Any error messages you've seen\n\nThis will help me assist you much faster.",
        )