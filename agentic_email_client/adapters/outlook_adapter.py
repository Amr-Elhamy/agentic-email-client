"""
Microsoft Graph API Outlook/Exchange Online Adapter with OAuth2 authentication.

Supports Microsoft 365 email via the Graph API for reading, sending, and managing emails.
"""

import asyncio
import base64
import json
from datetime import datetime, timezone
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any, AsyncIterator
from urllib.parse import urlencode
import aiohttp
import re

from .base import EmailAdapter, EmailMessage, EmailThread, EmailAttachment, EmailStatus, OAuthToken


class OutlookAdapter(EmailAdapter):
    """Microsoft Graph API adapter with full OAuth2 support for Outlook/Exchange Online."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: Optional[str] = None,
        redirect_uri: str = "http://localhost:8080/oauth/callback",
        scopes: Optional[List[str]] = None,
    ):
        super().__init__(client_id, client_secret, redirect_uri)
        self.tenant_id = tenant_id or "common"
        self.scopes = scopes or [
            "https://graph.microsoft.com/.default",
            "Mail.Read",
            "Mail.ReadWrite",
            "Mail.Send",
            "Mail.ReadBasic",
            " offline_access",
        ]
        self._session = aiohttp.ClientSession()
        self._graph_url = "https://graph.microsoft.com/v1.0"

    @property
    def auth_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize"

    @property
    def token_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

    def _get_scopes_string(self) -> str:
        return " ".join(self.scopes)

    async def get_authorization_url(self) -> str:
        """Generate OAuth2 authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self._get_scopes_string(),
            "response_type": "code",
            "prompt": "consent",
            "response_mode": "query",
        }
        return f"{self.auth_url}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> OAuthToken:
        """Exchange authorization code for access token."""
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
            "code": code,
            "scope": self._get_scopes_string(),
        }

        async with self._session.post(self.token_url, data=data) as response:
            result = await response.json()

        self.token = OAuthToken(
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token", ""),
            expires_at=datetime.now(timezone.utc)
            .replace(tzinfo=None)
            .timestamp()
            + result["expires_in"],
            scope=result.get("scope", ""),
            token_type=result.get("token_type", "Bearer"),
        )

        return self.token

    async def refresh_token(self) -> OAuthToken:
        """Refresh expired access token."""
        if not self.token or not self.token.refresh_token:
            raise Exception("No refresh token available")

        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "refresh_token",
            "refresh_token": self.token.refresh_token,
            "scope": self._get_scopes_string(),
        }

        async with self._session.post(self.token_url, data=data) as response:
            result = await response.json()

        self.token.access_token = result["access_token"]
        if "refresh_token" in result:
            self.token.refresh_token = result["refresh_token"]
        self.token.expires_at = datetime.now(timezone.utc).timestamp() + result["expires_in"]

        return self.token

    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        if not self.token:
            raise Exception("Not authenticated")
        return {
            "Authorization": f"Bearer {self.token.access_token}",
            "Content-Type": "application/json",
        }

    async def _graph_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make a Graph API request."""
        headers = self._get_headers()
        url = f"{self._graph_url}/{endpoint}"

        async with self._session.request(method, url, headers=headers, json=data) as response:
            if response.status >= 400:
                error_text = await response.text()
                raise Exception(f"Graph API error {response.status}: {error_text}")
            return await response.json()

    async def get_messages(
        self,
        query: str = "",
        max_results: int = 100,
        status: Optional[EmailStatus] = None,
        before: Optional[datetime] = None,
        after: Optional[datetime] = None,
    ) -> List[EmailMessage]:
        """Fetch emails matching criteria."""
        # Build filter
        filter_parts = [f"contains(subject,'{query}')"] if query else []

        if before:
            filter_parts.append(f"receivedDateTime le {before.isoformat()}")
        if after:
            filter_parts.append(f"receivedDateTime ge {after.isoformat()}")
        if status == EmailStatus.UNREAD:
            filter_parts.append("isRead eq false")
        elif status == EmailStatus.ARCHIVED:
            filter_parts.append("isArchived eq true")

        filter_str = " and ".join(filter_parts) if filter_parts else None

        try:
            result = await self._graph_request(
                "GET",
                "me/messages",
            )

            messages_raw = result.get("value", [])[:max_results]
            messages = [self._parse_message(msg) for msg in messages_raw]

            return messages

        except Exception as e:
            print(f"Error fetching messages: {e}")
            return []

    def _parse_message(self, msg: Dict) -> EmailMessage:
        """Parse Microsoft Graph message to EmailMessage."""
        from email.utils import parseaddr

        from_header = msg.get("from", {}).get("emailAddress", {})
        from_email = from_header.get("address", "")
        from_name = from_header.get("name")

        # Parse recipients
        to = []
        for rcpt in msg.get("toRecipients", []):
            email_addr = rcpt.get("emailAddress", {})
            to.append({"email": email_addr.get("address", ""), "name": email_addr.get("name")})

        # Parse body
        body_plain = None
        body_html = None

        if msg.get("bodyPreview"):
            body_plain = msg["bodyPreview"]

        if msg.get("body"):
            body_type = msg.get("body", {}).get("contentType", "text")
            body_content = msg.get("body", {}).get("content", "")
            if body_type == "html":
                body_html = body_content
            else:
                body_plain = body_content

        # Get status
        status = EmailStatus.UNREAD if not msg.get("isRead", False) else EmailStatus.READ
        if msg.get("isArchived", False):
            status = EmailStatus.ARCHIVED

        # Parse attachments
        attachments = []
        for att in msg.get("attachments", []):
            attachments.append(EmailAttachment(
                filename=att.get("name", "unknown"),
                content_type=att.get("contentType", "application/octet-stream"),
                size=att.get("size", 0),
            ))

        # Parse date
        date_str = msg.get("receivedDateTime", "")
        try:
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            date = datetime.now(timezone.utc)

        return EmailMessage(
            id=msg.get("id", ""),
            thread_id=msg.get("conversationId", ""),
            from_email=from_email,
            from_name=from_name,
            to=to,
            subject=msg.get("subject", ""),
            body_plain=body_plain,
            body_html=body_html,
            date=date,
            status=status,
            attachments=attachments,
        )

    async def get_thread(self, thread_id: str) -> EmailThread:
        """Get complete thread by conversation ID."""
        try:
            result = await self._graph_request(
                "GET",
                f"me/conversations/{thread_id}",
            )

            conversations = result.get("conversations", [])
            all_messages = []

            for conv in conversations:
                threads = conv.get("threads", [])
                for thread in threads:
                    posts = thread.get("posts", [])
                    for post in posts:
                        msg = self._parse_message(post)
                        msg.thread_id = thread_id
                        all_messages.append(msg)

            participants = list(set([
                m.from_email for m in all_messages if m.from_email
            ] + [
                t["email"] for m in all_messages for t in m.to
            ]))

            return EmailThread(
                id=thread_id,
                subject=all_messages[0].subject if all_messages else "",
                messages=all_messages,
                participants=participants,
                created_at=all_messages[-1].date if all_messages else datetime.now(timezone.utc),
                updated_at=all_messages[0].date if all_messages else datetime.now(timezone.utc),
            )

        except Exception as e:
            print(f"Error fetching thread: {e}")
            raise

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
        try:
            message_body = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML" if html_body else "Text",
                        "content": html_body if html_body else body,
                    },
                    "toRecipients": [{"emailAddress": {"address": to}}],
                },
                "saveToSentItems": True,
            }

            if reply_to:
                message_body["message"]["replyTo"] = {"emailAddress": {"address": reply_to}}

            if attachments:
                message_body["message"]["attachments"] = [
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": att.filename,
                        "contentType": att.content_type,
                        "isInline": False,
                    }
                    for att in attachments
                ]

            result = await self._graph_request("POST", "me/sendMail", data=message_body)

            return result.get("id", "")

        except Exception as e:
            print(f"Error sending message: {e}")
            raise

    async def reply_to_message(
        self,
        message_id: str,
        body: str,
        html_body: Optional[str] = None,
        in_reply_to: bool = True,
    ) -> str:
        """Reply to specific message."""
        try:
            if not html_body:
                html_body = body.replace("\n", "<br>")

            message_body = {
                "message": {
                    "subject": f"Re: {body}",
                    "body": {
                        "contentType": "HTML",
                        "content": html_body,
                    },
                    "toRecipients": [{"emailAddress": {"address": "recipient@example.com"}}],
                }
            }

            result = await self._graph_request("POST", f"me/messages/{message_id}/reply", data=message_body)

            return result

        except Exception as e:
            print(f"Error replying to message: {e}")
            raise

    async def label_message(self, message_id: str, labels: List[str]) -> None:
        """Add categories/labels to message."""
        try:
            await self._graph_request("POST", f"me/messages/{message_id}/addCategories", data={"categories": labels})
        except Exception as e:
            print(f"Error labeling message: {e}")
            raise

    async def archive_message(self, message_id: str) -> None:
        """Move message to archive (move to Deleted Items then restore)."""
        try:
            # Microsoft Graph has different archive concept
            # For now, mark as read and move conversation
            await self._graph_request("PATCH", f"me/messages/{message_id}", data={"isArchived": True})
        except Exception as e:
            print(f"Error archiving message: {e}")
            raise

    async def delete_message(self, message_id: str) -> None:
        """Delete message."""
        try:
            await self._graph_request("DELETE", f"me/messages/{message_id}")
        except Exception as e:
            print(f"Error deleting message: {e}")
            raise

    async def stream_notifications(self) -> AsyncIterator[Dict[str, Any]]:
        """Stream email notifications via polling (Microsoft Graph uses webhook subscriptions)."""
        latest_timestamp = None

        while True:
            try:
                params = {}
                if latest_timestamp:
                    params["$filter"] = f"receivedDateTime gt {latest_timestamp}"

                result = await self._graph_request("GET", "me/messages", data=params)

                messages = result.get("value", [])
                for msg in messages:
                    yield {
                        "type": "messageReceived",
                        "data": msg,
                    }

                if messages:
                    latest_timestamp = max(m.get("receivedDateTime") for m in messages)

                await asyncio.sleep(10)

            except Exception as e:
                print(f"Streaming error: {e}")
                await asyncio.sleep(30)

    def _decode_base64(self, data: str) -> str:
        """Decode base64 encoded data."""
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    async def close(self):
        """Close connections."""
        await self._session.close()


# Convenience function to create adapter
def create_outlook_adapter(
    client_id: str,
    client_secret: str,
    tenant_id: Optional[str] = None,
    redirect_uri: str = "http://localhost:8080/oauth/callback",
) -> OutlookAdapter:
    """Create Outlook adapter with provided credentials."""
    return OutlookAdapter(client_id, client_secret, tenant_id, redirect_uri)