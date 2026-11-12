"""
Gmail API Adapter with OAuth2 authentication.

Supports Gmail v1 API for reading, sending, and managing emails.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, AsyncIterator
from urllib.parse import urlencode
import aiohttp
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .base import EmailAdapter, EmailMessage, EmailThread, EmailAttachment, EmailStatus, OAuthToken


class GmailAdapter(EmailAdapter):
    """Gmail API adapter with full OAuth2 support."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://localhost:8080/oauth/callback",
        scopes: Optional[List[str]] = None,
    ):
        super().__init__(client_id, client_secret, redirect_uri)
        self.scopes = scopes or [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/gmail.compose",
        ]
        self._service = None
        self._session = aiohttp.ClientSession()

    @property
    def auth_url(self) -> str:
        return "https://accounts.google.com/o/oauth2/auth"

    @property
    def token_url(self) -> str:
        return "https://oauth2.googleapis.com/token"

    def _get_scopes_string(self) -> str:
        return " ".join(self.scopes)

    async def get_authorization_url(self) -> str:
        """Generate OAuth2 authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self._get_scopes_string(),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "response_type": "code",
            "prompt": "consent",  # Ensure refresh token is returned
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
        }

        async with self._session.post(self.token_url, data=data) as response:
            result = await response.json()

        self.token = OAuthToken(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            expires_at=datetime.now(timezone.utc)
            .replace(tzinfo=None)
            .timestamp()
            + result["expires_in"],
            scope=result.get("scope", ""),
            token_type=result.get("token_type", "Bearer"),
        )

        await self._update_service()
        return self.token

    async def refresh_token(self) -> OAuthToken:
        """Refresh expired access token."""
        if not self.token or not self.token.refresh_token:
            raise Exception("No refresh token available")

        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.token.refresh_token,
            "grant_type": "refresh_token",
        }

        async with self._session.post(self.token_url, data=data) as response:
            result = await response.json()

        self.token.access_token = result["access_token"]
        self.token.expires_at = datetime.now(timezone.utc).timestamp() + result["expires_in"]

        return self.token

    async def _update_service(self):
        """Update Google API service with current credentials."""
        if not self.token:
            raise Exception("Not authenticated")

        creds = Credentials(
            token=self.token.access_token,
            refresh_token=self.token.refresh_token,
            token_uri=self.token_url,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )

        # Refresh if needed
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        self._service = build("gmail", "v1", credentials=creds)

    async def get_messages(
        self,
        query: str = "",
        max_results: int = 100,
        status: Optional[EmailStatus] = None,
        before: Optional[datetime] = None,
        after: Optional[datetime] = None,
    ) -> List[EmailMessage]:
        """Fetch emails matching criteria."""
        if not self._service:
            await self._update_service()

        # Build query
        full_query = query
        if before:
            full_query += f" before:{before.strftime('%Y/%m/%d')}"
        if after:
            full_query += f" after:{after.strftime('%Y/%m/%d')}"
        if status == EmailStatus.UNREAD:
            full_query += " is:unread"
        elif status == EmailStatus.ARCHIVED:
            full_query += " is:archived"

        try:
            # List messages
            results = self._service.users().messages().list(
                userId="me",
                q=full_query if full_query else None,
                maxResults=max_results,
            ).execute()

            message_ids = [m["id"] for m in results.get("messages", [])]

            # Fetch message details
            messages = []
            for msg_id in message_ids:
                msg = self._service.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="FULL",
                ).execute()
                messages.append(self._parse_message(msg))

            return messages

        except HttpError as error:
            print(f"An error occurred: {error}")
            return []

    def _parse_message(self, msg: Dict) -> EmailMessage:
        """Parse raw Gmail message to EmailMessage."""
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

        # Get status
        status = EmailStatus.UNREAD if "UNREAD" in msg.get("labelIds", []) else EmailStatus.READ
        if "INBOX" not in msg.get("labelIds", []):
            status = EmailStatus.ARCHIVED

        # Parse body
        body_plain = None
        body_html = None
        for part in msg.get("payload", {}).get("parts", []):
            if part.get("mimeType") == "text/plain":
                body_plain = part.get("body", {}).get("data", "")
            elif part.get("mimeType") == "text/html":
                body_html = part.get("body", {}).get("data", "")

        # If no parts, check the body directly
        if not body_plain and msg.get("payload", {}).get("body"):
            body_plain = msg["payload"]["body"].get("data", "")

        # Parse attachments
        attachments = []
        for part in msg.get("payload", {}).get("parts", []):
            if part.get("filename"):
                attachments.append(EmailAttachment(
                    filename=part["filename"],
                    content_type=part.get("mimeType", ""),
                    size=part.get("body", {}).get("size", 0),
                ))

        # Parse date
        date_str = headers.get("Date", "")
        try:
            date = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            date = datetime.now(timezone.utc)

        return EmailMessage(
            id=msg["id"],
            thread_id=msg.get("threadId", ""),
            from_email=headers.get("From", "").split("<")[-1].rstrip(">") if "From" in headers else "",
            from_name=headers.get("From", "").split("<")[0].strip().rstrip('"') if "From" in headers else None,
            to=[{"email": h["value"], "name": h.get("name")} for h in msg.get("payload", {}).get("headers", []) if h["name"] == "To"],
            subject=headers.get("Subject", ""),
            body_plain=body_plain,
            body_html=body_html,
            date=date,
            status=status,
            attachments=attachments,
            labels=msg.get("labelIds", []),
            raw_headers={h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])},
        )

    async def get_thread(self, thread_id: str) -> EmailThread:
        """Get complete thread by thread ID."""
        if not self._service:
            await self._update_service()

        try:
            thread = self._service.users().threads().get(
                userId="me",
                id=thread_id,
                format="FULL",
            ).execute()

            messages = [self._parse_message(m) for m in thread.get("messages", [])]
            participants = list(set([
                m.from_email for m in messages
                if m.from_email
            ] + [
                t["email"] for m in messages for t in m.to
            ]))

            return EmailThread(
                id=thread_id,
                subject=messages[0].subject if messages else "",
                messages=messages,
                participants=participants,
                created_at=messages[-1].date if messages else datetime.now(timezone.utc),
                updated_at=messages[0].date if messages else datetime.now(timezone.utc),
            )

        except HttpError as error:
            print(f"An error occurred: {error}")
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
        if not self._service:
            await self._update_service()

        try:
            from email.mime.base import MIMEBase
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            import base64

            message = MIMEMultipart()
            message["To"] = to
            message["Subject"] = subject

            if reply_to:
                message["Reply-To"] = reply_to

            if html_body:
                message.attach(MIMEText(html_body, "html"))
            message.attach(MIMEText(body, "plain"))

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            result = self._service.users().messages().send(
                userId="me",
                body={"raw": raw},
            ).execute()

            return result["id"]

        except HttpError as error:
            print(f"An error occurred: {error}")
            raise

    async def reply_to_message(
        self,
        message_id: str,
        body: str,
        html_body: Optional[str] = None,
        in_reply_to: bool = True,
    ) -> str:
        """Reply to specific message."""
        if not self._service:
            await self._update_service()

        try:
            # Get original message for threading
            original = self._service.users().messages().get(
                userId="me",
                id=message_id,
                format="FULL",
            ).execute()

            headers = {h["name"]: h["value"] for h in original.get("payload", {}).get("headers", [])}
            from_email = headers.get("From", "")
            subject = headers.get("Subject", "")

            # Add Re: prefix if needed
            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"

            return await self.send_message(
                to=from_email,
                subject=subject,
                body=body,
                html_body=html_body,
                reply_to=message_id if in_reply_to else None,
            )

        except HttpError as error:
            print(f"An error occurred: {error}")
            raise

    async def label_message(self, message_id: str, labels: List[str]) -> None:
        """Add labels to message."""
        if not self._service:
            await self._update_service()

        try:
            self._service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": labels},
            ).execute()
        except HttpError as error:
            print(f"An error occurred: {error}")
            raise

    async def archive_message(self, message_id: str) -> None:
        """Move message to archive."""
        if not self._service:
            await self._update_service()

        try:
            self._service.users().messages().trash(
                userId="me",
                id=message_id,
            ).execute()
        except HttpError as error:
            print(f"An error occurred: {error}")
            raise

    async def delete_message(self, message_id: str) -> None:
        """Delete message."""
        if not self._service:
            await self._update_service()

        try:
            self._service.users().messages().delete(
                userId="me",
                id=message_id,
            ).execute()
        except HttpError as error:
            print(f"An error occurred: {error}")
            raise

    async def stream_notifications(self) -> AsyncIterator[Dict[str, Any]]:
        """Stream email notifications via polling (Gmail uses push but requires setup)."""
        last_history_id = 0

        while True:
            try:
                if not self._service:
                    await self._update_service()

                result = self._service.users().history().list(
                    userId="me",
                    startHistoryId=last_history_id,
                ).execute()

                for history in result.get("history", []):
                    for change in history.get("historyChanges", []):
                        yield change

                last_history_id = result.get("historyId", 0) + 1
                await asyncio.sleep(5)  # Polling interval

            except Exception as e:
                print(f"Streaming error: {e}")
                await asyncio.sleep(30)

    async def close(self):
        """Close connections."""
        await self._session.close()


# Convenience function to create adapter
def create_gmail_adapter(
    client_id: str,
    client_secret: str,
    redirect_uri: str = "http://localhost:8080/oauth/callback",
) -> GmailAdapter:
    """Create Gmail adapter with provided credentials."""
    return GmailAdapter(client_id, client_secret, redirect_uri)