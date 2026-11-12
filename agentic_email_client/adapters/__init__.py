"""
Email Provider Adapters

Supports Gmail and Outlook/Microsoft 365 email providers.
"""

from .base import EmailAdapter, EmailMessage, EmailThread, EmailStatus, EmailAttachment, OAuthToken
from .gmail_adapter import GmailAdapter, create_gmail_adapter
from .outlook_adapter import OutlookAdapter, create_outlook_adapter

__all__ = [
    "GmailAdapter",
    "OutlookAdapter",
    "EmailAdapter",
    "EmailMessage",
    "EmailThread",
    "EmailStatus",
    "EmailAttachment",
    "OAuthToken",
    "create_gmail_adapter",
    "create_outlook_adapter",
]