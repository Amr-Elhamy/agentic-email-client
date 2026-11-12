#!/usr/bin/env python
"""
Test script to verify the agent framework compiles and works correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))
from datetime import datetime, timezone

from agentic_email_client.adapters import (
    EmailMessage,
    EmailStatus,
    EmailThread,
    EmailAttachment,
)
from agentic_email_client.memory import VectorMemory
from agentic_email_client.agents import (
    BaseEmailAgent,
    SalesAgent,
    SupportAgent,
    OperationsAgent,
    AgentRole,
    AgentAction,
    AgentDecision,
)


async def test_vector_memory():
    """Test VectorMemory functionality."""
    print("Testing VectorMemory...")
    memory = VectorMemory()

    # Store an entry
    entry_id = await memory.store(
        query="test email about pricing",
        metadata={"type": "email", "priority": "high"},
    )
    print(f"  Stored entry with ID: {entry_id[:16]}...")

    # Search for entries
    results = await memory.search("pricing")
    print(f"  Found {len(results)} results for 'pricing'")

    # Get specific entry
    entry = await memory.get(entry_id)
    print(f"  Retrieved entry: {entry['query'][:30]}...")

    assert len(memory) == 1, "Memory should have 1 entry"
    print("  [OK] VectorMemory tests passed\n")


async def test_email_message():
    """Test EmailMessage dataclass."""
    print("Testing EmailMessage...")

    msg = EmailMessage(
        id="test123",
        thread_id="thread456",
        from_email="sender@example.com",
        from_name="Test Sender",
        to=[{"email": "recipient@example.com", "name": "Recipient"}],
        subject="Test Subject",
        body_plain="This is a test email body.",
        body_html="<p>This is a test email body.</p>",
        date=datetime.now(timezone.utc),
        status=EmailStatus.UNREAD,
    )

    print(f"  Created message: {msg.subject}")
    print(f"  From: {msg.from_name} ({msg.from_email})")
    print(f"  Status: {msg.status.value}")
    print("  [OK] EmailMessage tests passed\n")


async def test_sales_agent():
    """Test SalesAgent functionality."""
    print("Testing SalesAgent...")

    memory = VectorMemory()
    agent = SalesAgent(memory=memory)

    # Test email filters
    print(f"  Role: {agent.role.value}")
    print(f"  Email filters: {agent.email_filters[:3]}...")

    # Create test email
    email = EmailMessage(
        id="sale001",
        thread_id="thread001",
        from_email="lead@example.com",
        from_name="Prospective Lead",
        to=[{"email": "sales@company.com", "name": "Sales Team"}],
        subject="Inquiry about pricing",
        body_plain="Hi, I'm interested in learning about your pricing options.",
        body_html="<p>Hi, I'm interested in learning about your pricing options.</p>",
        date=datetime.now(timezone.utc),
        status=EmailStatus.UNREAD,
    )

    # Check eligibility
    eligible = await agent.is_eligible_for_email(email)
    print(f"  Eligible for email: {eligible}")

    # Make decision
    context = {"email": email, "role": agent.role.value, "history": [], "timestamp": datetime.now().isoformat()}
    decision = await agent._make_decision(context)
    print(f"  Decision: {decision.action.value} (confidence: {decision.confidence})")
    print(f"  Reason: {decision.reason}")

    assert eligible, "Sales agent should be eligible for pricing inquiry"
    assert decision.action == AgentAction.REPLY, "Should reply to pricing inquiry"
    print("  [OK] SalesAgent tests passed\n")


async def test_support_agent():
    """Test SupportAgent functionality."""
    print("Testing SupportAgent...")

    memory = VectorMemory()
    agent = SupportAgent(memory=memory)

    # Create test email
    email = EmailMessage(
        id="support001",
        thread_id="thread001",
        from_email="customer@example.com",
        from_name="Customer",
        to=[{"email": "support@company.com", "name": "Support Team"}],
        subject="I can't access my account",
        body_plain="I'm having trouble logging in. It says my password is incorrect but I've tried multiple times.",
        body_html="<p>I'm having trouble logging in...</p>",
        date=datetime.now(timezone.utc),
        status=EmailStatus.UNREAD,
    )

    eligible = await agent.is_eligible_for_email(email)
    print(f"  Eligible for email: {eligible}")

    context = {"email": email, "role": agent.role.value, "history": [], "timestamp": datetime.now().isoformat()}
    decision = await agent._make_decision(context)
    print(f"  Decision: {decision.action.value} (confidence: {decision.confidence})")

    assert eligible, "Support agent should be eligible for account access issue"
    print("  [OK] SupportAgent tests passed\n")


async def test_operations_agent():
    """Test OperationsAgent functionality."""
    print("Testing OperationsAgent...")

    memory = VectorMemory()
    agent = OperationsAgent(memory=memory)

    # Create test email
    email = EmailMessage(
        id="ops001",
        thread_id="thread001",
        from_email="newhire@example.com",
        from_name="New Hire",
        to=[{"email": "operations@company.com", "name": "Operations Team"}],
        subject="New employee onboarding request",
        body_plain="I need to get set up for my new role starting next Monday.",
        body_html="<p>I need to get set up...</p>",
        date=datetime.now(timezone.utc),
        status=EmailStatus.UNREAD,
    )

    eligible = await agent.is_eligible_for_email(email)
    print(f"  Eligible for email: {eligible}")

    context = {"email": email, "role": agent.role.value, "history": [], "timestamp": datetime.now().isoformat()}
    decision = await agent._make_decision(context)
    print(f"  Decision: {decision.action.value} (confidence: {decision.confidence})")
    print(f"  Labels: {decision.labels}")

    assert eligible, "Operations agent should be eligible for onboarding request"
    print("  [OK] OperationsAgent tests passed\n")


async def main():
    """Run all tests."""
    print("\n" + "="*50)
    print("Agent Framework Integration Tests")
    print("="*50 + "\n")

    await test_vector_memory()
    await test_email_message()
    await test_sales_agent()
    await test_support_agent()
    await test_operations_agent()

    print("="*50)
    print("All tests passed! [OK]")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(main())