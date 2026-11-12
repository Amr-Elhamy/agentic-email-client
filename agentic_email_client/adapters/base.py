"""
Base adapter interface for email providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, AsyncIterator


class EmailStatus(Enum):
    READ = "read"
    UNREAD = "unread"
    ARCHIVED = "archived"
    TRASH = "trash"


@dataclass
class EmailAttachment:
    filename: str
    content_type: str
    size: int
    url: Optional[str] = None


@dataclass
class EmailMessage:
    id: str
    thread_id: str
    from_email: str
    from_name: Optional[str]
    to: List[Dict[str, str]]
    subject: str
    body_plain: Optional[str]
    body_html: Optional[str]
    date: datetime
    status: EmailStatus
    attachments: List[EmailAttachment] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    raw_headers: Dict[str, str] = field(default_factory=dict)

    class Config:
        json_mode = True


@dataclass
class EmailThread:
    id: str
    subject: str
    messages: List[EmailMessage]
    participants: List[str]
    created_at: datetime
    updated_at: datetime
    is_locked: bool = False


@dataclass
class OAuthToken:
    access_token: str
    refresh_token: str
    expires_at: datetime
    scope: str
    token_type: str = "Bearer"


class EmailAdapter(ABC):
    """Base interface for email provider adapters."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token: Optional[OAuthToken] = None

    @abstractmethod
    async def get_authorization_url(self) -> str:
        """Generate OAuth2 authorization URL."""
        pass

    @abstractmethod
    async def exchange_code(self, code: str) -> OAuthToken:
        """Exchange authorization code for access token."""
        pass

    @abstractmethod
    async def refresh_token(self) -> OAuthToken:
        """Refresh expired access token."""
        pass

    @abstractmethod
    async def get_messages(
        self,
        query: str = "",
        max_results: int = 100,
        status: Optional[EmailStatus] = None,
        before: Optional[datetime] = None,
        after: Optional[datetime] = None,
    ) -> List[EmailMessage]:
        """Fetch emails matching criteria."""
        pass

    @abstractmethod
    async def get_thread(self, thread_id: str) -> EmailThread:
        """Get complete thread by thread ID."""
        pass

    @abstractmethod
    async def send_message(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[EmailAttachment]] = None,
    ) -> str:
        """Send email and return message ID."""
        pass

    @abstractmethod
    async def reply_to_message(
        self,
        message_id: str,
        body: str,
        html_body: Optional[str] = None,
        in_reply_to: bool = True,
    ) -> str:
        """Reply to specific message."""
        pass

    @abstractmethod
    async def label_message(self, message_id: str, labels: List[str]) -> None:
        """Add labels to message."""
        pass

    @abstractmethod
    async def archive_message(self, message_id: str) -> None:
        """Move message to archive."""
        pass

    @abstractmethod
    async def delete_message(self, message_id: str) -> None:
        """Delete message."""
        pass

    @abstractmethod
    def stream_notifications(self) -> AsyncIterator[Dict[str, Any]]:
        """Stream email notifications via webhook/poll."""
        pass

    def _ensure_authenticated(self) -> None:
        """Ensure valid authentication."""
        if self.token is None or self.token.access_token is None:
            raise Exception("Not authenticated")