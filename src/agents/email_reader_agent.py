"""
Email Reader Agent
Fetches and reads emails from Gmail using Gmail API
"""

import base64
import logging
import os
from typing import Dict, List

# Security limits
MAX_EMAIL_BODY_SIZE = 1_000_000  # 1MB max email body to prevent DoS
MAX_ATTACHMENT_SIZE = 10_000_000  # 10MB max attachment

# Gmail API Scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

# Token file path
TOKEN_PATH = os.environ.get("GMAIL_TOKEN_PATH", "config/token.json")
CREDENTIALS_PATH = os.environ.get("GMAIL_CLIENT_SECRET", "config/credentials.json")
logger = logging.getLogger(__name__)


class EmailReaderAgent:
    """
    Agent responsible for reading emails from Gmail inbox
    Uses Gmail API for OAuth2 authentication and email fetching
    """

    def __init__(self):
        self.credentials = None
        self.service = None
        self.token_file = TOKEN_PATH
        self.credentials_file = CREDENTIALS_PATH

    def authenticate(self) -> bool:
        """
        Authenticate with Gmail API using OAuth2
        Returns True if authentication is successful
        """
        try:
            # Try to import Google API libraries
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow

            # Load credentials from token file if it exists
            if os.path.exists(self.token_file):
                self.credentials = Credentials.from_authorized_user_file(
                    self.token_file, SCOPES
                )

            # If no valid credentials, try refresh or run OAuth2 flow
            if not self.credentials or not self.credentials.valid:
                if (
                    self.credentials
                    and self.credentials.expired
                    and self.credentials.refresh_token
                ):
                    logger.info("Refreshing expired Gmail token...")
                    self.credentials.refresh(Request())
                else:
                    if not os.path.exists(self.credentials_file):
                        logger.error(
                            "Gmail credentials file not found: %s. "
                            "Run: python src/gmail/token_manager.py auth",
                            self.credentials_file,
                        )
                        return False
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES
                    )
                    try:
                        self.credentials = flow.run_local_server(port=8080, open_browser=True)
                    except OSError as e:
                        # Fallback for headless/Docker environments
                        logger.warning(
                            "Local server auth failed (headless env?): %s. "
                            "Use: python src/gmail/token_manager.py auth",
                            e,
                        )
                        return False

                # Save the credentials for the next run
                try:
                    os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
                except (OSError, ValueError):
                    pass  # Directory may already exist or path is empty
                with open(self.token_file, "w") as token:
                    token.write(self.credentials.to_json())
                try:
                    os.chmod(self.token_file, 0o600)
                except OSError:
                    pass  # Windows doesn't support Unix permissions

            # Build the Gmail service
            from googleapiclient.discovery import build

            self.service = build("gmail", "v1", credentials=self.credentials)
            return True

        except ImportError as e:
            logger.error(
                "Google API libraries not installed. Install: "
                "pip install google-auth google-auth-oauthlib google-api-python-client"
            )
            return False
        except Exception as e:
            logger.error("Authentication error: %s", e)
            return False

    def get_unread_emails(self, max_results: int = 50) -> List[Dict]:
        """
        Fetch unread emails from Gmail inbox
        Returns list of email data dictionaries
        """
        if not self.service:
            if not self.authenticate():
                return []

        try:
            # Search for unread emails
            results = (
                self.service.users()
                .messages()
                .list(userId="me", q="is:unread", maxResults=max_results)
                .execute()
            )

            messages = results.get("messages", [])
            emails = []

            for message in messages:
                msg = (
                    self.service.users()
                    .messages()
                    .get(userId="me", id=message["id"], format="full")
                    .execute()
                )
                email_data = self.parse_email_message(msg)
                email_data["message_id"] = message["id"]
                emails.append(email_data)

            return emails

        except Exception as e:
            logger.error("Error fetching emails: %s", e)
            return []

    def get_emails_by_subject_keyword(
        self, keywords: List[str], max_results: int = 50
    ) -> List[Dict]:
        """
        Fetch emails matching specific subject keywords
        Used for filtering emails before processing
        """
        if not self.service:
            if not self.authenticate():
                return []

        try:
            # Build query string
            query = (
                "is:unread ("
                + " OR ".join([f'subject:"{keyword}"' for keyword in keywords])
                + ")"
            )

            results = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )

            messages = results.get("messages", [])
            emails = []

            for message in messages:
                msg = (
                    self.service.users()
                    .messages()
                    .get(userId="me", id=message["id"], format="full")
                    .execute()
                )
                email_data = self.parse_email_message(msg)
                email_data["message_id"] = message["id"]
                emails.append(email_data)

            return emails

        except Exception as e:
            logger.error("Error fetching emails by keyword: %s", e)
            return []

    def parse_email_message(self, msg: Dict) -> Dict:
        """
        Parse raw email message into structured data
        """
        from email.header import decode_header

        email_data = {}

        # Get headers
        headers = msg.get("payload", {}).get("headers", [])
        for header in headers:
            name = header.get("name", "").lower()
            value = header.get("value", "")

            if name == "from":
                email_data["from"] = value
                # Extract email address
                if "<" in value:
                    email_data["from_email"] = value.split("<")[1].split(">")[0].strip()
                else:
                    email_data["from_email"] = value

            elif name == "subject":
                email_data["subject"] = self.decode_header_value(value)
            elif name == "to":
                email_data["to"] = value
                if "<" in value:
                    email_data["to_email"] = value.split("<")[1].split(">")[0].strip()
                else:
                    email_data["to_email"] = value

            elif name == "date":
                email_data["date"] = value

            elif name == "message-id":
                email_data["message_id_header"] = value

        # Get email body
        email_data["body"] = self.get_email_body(msg)
        email_data["attachments"] = self.get_email_attachments(msg)

        return email_data

    def get_email_body(self, msg: Dict) -> str:
        """
        Extract email body text from message
        """
        payload = msg.get("payload")
        if not payload:
            return ""
        body = self._extract_body_from_part(payload).strip()
        # Security: Limit body size to prevent DoS
        if len(body) > MAX_EMAIL_BODY_SIZE:
            logger.warning(f"Email body exceeds size limit ({len(body)} > {MAX_EMAIL_BODY_SIZE}). Truncating.")
            body = body[:MAX_EMAIL_BODY_SIZE] + "\n\n[Email body truncated due to size limit]"
        return body

    def _extract_body_from_part(self, part: Dict) -> str:
        """
        Recursively extract the best body candidate from MIME parts.
        Prefers text/plain, falls back to text/html, then traverses children.
        """
        if not part:
            return ""

        mime_type = part.get("mimeType", "")
        data = part.get("body", {}).get("data", "")
        children = part.get("parts", []) or []

        if mime_type == "text/plain" and data:
            return self._decode_base64_data(data)

        if mime_type == "text/html" and data:
            return self._decode_base64_data(data)

        for child in children:
            extracted = self._extract_body_from_part(child)
            if extracted:
                return extracted

        if data:
            return self._decode_base64_data(data)

        return ""

    def _decode_base64_data(self, data: str) -> str:
        """Decode Gmail base64url-encoded payload safely."""
        if not data:
            return ""
        try:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        except Exception:
            return ""

    def get_email_attachments(self, msg: Dict) -> List[Dict]:
        """
        Extract email attachments
        Returns list of attachment metadata
        """
        attachments = []

        def walk_parts(part: Dict):
            if not part:
                return

            filename = part.get("filename", "")
            attachment_id = part.get("body", {}).get("attachmentId", "")
            if filename and attachment_id:
                attachments.append(
                    {
                        "filename": filename,
                        "mimeType": part.get("mimeType", ""),
                        "attachmentId": attachment_id,
                    }
                )

            for child in part.get("parts", []) or []:
                walk_parts(child)

        if "payload" in msg:
            walk_parts(msg["payload"])

        return attachments

    def download_attachment_data(self, message_id: str, attachment_id: str) -> bytes:
        """Download attachment bytes for a Gmail message attachment id."""
        if not self.service:
            if not self.authenticate():
                return b""

        if not message_id or not attachment_id:
            return b""

        try:
            response = (
                self.service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=attachment_id)
                .execute()
            )
            data = response.get("data", "")
            if not data:
                return b""
            decoded = base64.urlsafe_b64decode(data)
            # Security: Limit attachment size
            if len(decoded) > MAX_ATTACHMENT_SIZE:
                logger.warning(f"Attachment exceeds size limit ({len(decoded)} > {MAX_ATTACHMENT_SIZE}). Skipping.")
                return b""
            return decoded
        except Exception as e:
            logger.error("Error downloading attachment data: %s", e)
            return b""

    def decode_header_value(self, value: str) -> str:
        """
        Decode encoded header values
        """
        from email.header import decode_header

        decoded_parts = decode_header(value)
        decoded_string = ""

        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    decoded_string += part.decode(encoding or "utf-8", errors="replace")
                except Exception:
                    decoded_string += part.decode("utf-8", errors="replace")
            else:
                decoded_string += part

        return decoded_string

    def mark_email_as_read(self, message_id: str) -> bool:
        """
        Mark an email as read after processing
        """
        if not self.service:
            return False

        try:
            self.service.users().messages().modify(
                userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return True
        except Exception as e:
            logger.error("Error marking email as read: %s", e)
            return False

    def mark_email_as_unread(self, message_id: str) -> bool:
        """
        Mark an email as unread (for reprocessing)
        """
        if not self.service:
            return False

        try:
            self.service.users().messages().modify(
                userId="me", id=message_id, body={"addLabelIds": ["UNREAD"]}
            ).execute()
            return True
        except Exception as e:
            logger.error("Error marking email as unread: %s", e)
            return False


# Test function
def test_email_reader():
    """Test the email reader agent"""
    reader = EmailReaderAgent()

    print("🔄 Authenticating with Gmail API...")
    if reader.authenticate():
        print("✅ Authentication successful!")
    else:
        print("❌ Authentication failed!")
        return

    print("\n🔍 Fetching unread emails...")
    emails = reader.get_unread_emails(max_results=5)

    if emails:
        print("\n📥 Found " + str(len(emails)) + " unread emails:\n")
        for i, email in enumerate(emails, 1):
            print(str(i) + ". From: " + email.get("from", "Unknown"))
            print("   Subject: " + email.get("subject", "No Subject"))
            print("   Body preview: " + email.get("body", "")[:100] + "...")
            attachments = email.get("attachments", [])
            if attachments:
                print("   Attachments: " + str([a["filename"] for a in attachments]))
            print()
    else:
        print("No unread emails found.")


if __name__ == "__main__":
    test_email_reader()
