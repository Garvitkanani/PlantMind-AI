"""
Gmail Token Manager
Handles OAuth2 token refresh, storage, and automatic renewal.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


class TokenManager:
    """
    Manages Gmail OAuth2 tokens with automatic refresh and secure storage.
    """

    def __init__(self, token_path: Optional[str] = None, credentials_path: Optional[str] = None):
        self.token_path = Path(token_path or os.environ.get("GMAIL_TOKEN_PATH", "config/token.json"))
        self.credentials_path = Path(credentials_path or os.environ.get("GMAIL_CLIENT_SECRET", "config/credentials.json"))
        self.credentials: Optional[Credentials] = None

    def load_credentials(self) -> Optional[Credentials]:
        """Load existing credentials from token file."""
        if not self.token_path.exists():
            logger.info("No existing token file found")
            return None

        try:
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            self.credentials = creds
            logger.info(f"Loaded credentials from {self.token_path}")
            return creds
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return None

    def save_credentials(self, creds: Credentials) -> bool:
        """Save credentials to token file with secure permissions."""
        try:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            
            token_data = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes,
                "expiry": creds.expiry.isoformat() if creds.expiry else None,
            }
            
            with open(self.token_path, "w") as f:
                json.dump(token_data, f, indent=2)
            
            # Set secure file permissions (owner read/write only)
            try:
                os.chmod(self.token_path, 0o600)
            except (OSError, NotImplementedError):
                pass  # Windows doesn't support Unix permissions
            
            logger.info(f"Saved credentials to {self.token_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            return False

    def refresh_if_needed(self) -> bool:
        """Refresh credentials if expired or about to expire."""
        if not self.credentials:
            logger.error("No credentials loaded")
            return False

        if not self.credentials.valid:
            if self.credentials.expired and self.credentials.refresh_token:
                try:
                    logger.info("Refreshing expired token...")
                    self.credentials.refresh(Request())
                    self.save_credentials(self.credentials)
                    logger.info("Token refreshed successfully")
                    return True
                except Exception as e:
                    logger.error(f"Failed to refresh token: {e}")
                    return False
            else:
                logger.error("Token expired and no refresh token available")
                return False

        # Check if token expires soon (within 5 minutes)
        if self.credentials.expiry:
            time_until_expiry = (self.credentials.expiry - datetime.now(timezone.utc)).total_seconds()
            if time_until_expiry < 300:  # 5 minutes
                logger.info(f"Token expires in {time_until_expiry}s, refreshing...")
                try:
                    self.credentials.refresh(Request())
                    self.save_credentials(self.credentials)
                    logger.info("Token refreshed proactively")
                    return True
                except Exception as e:
                    logger.warning(f"Proactive refresh failed: {e}")

        return True

    def authenticate_interactive(self) -> Optional[Credentials]:
        """Run interactive OAuth2 flow for initial authentication."""
        if not self.credentials_path.exists():
            logger.error(f"Credentials file not found: {self.credentials_path}")
            logger.error("Download from Google Cloud Console and save as config/credentials.json")
            return None

        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=True)
            
            self.credentials = creds
            self.save_credentials(creds)
            logger.info("Interactive authentication completed")
            return creds
        except Exception as e:
            logger.error(f"Interactive authentication failed: {e}")
            return None

    def get_valid_credentials(self) -> Optional[Credentials]:
        """Get valid credentials, refreshing if necessary."""
        if not self.credentials:
            self.load_credentials()
        
        if self.credentials and self.refresh_if_needed():
            return self.credentials
        
        return None

    def revoke(self) -> bool:
        """Revoke the current token."""
        if not self.credentials or not self.credentials.token:
            logger.warning("No token to revoke")
            return True

        try:
            import urllib.request
            import urllib.parse
            data = urllib.parse.urlencode({"token": self.credentials.token}).encode()
            req = urllib.request.Request(
                "https://oauth2.googleapis.com/revoke",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    logger.info("Token revoked successfully")
                    # Delete local token file
                    if self.token_path.exists():
                        self.token_path.unlink()
                        logger.info(f"Deleted token file: {self.token_path}")
                    self.credentials = None
                    return True
                else:
                    logger.error(f"Token revocation failed with status: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
            return False

    def get_token_info(self) -> dict:
        """Get information about the current token."""
        if not self.credentials:
            return {"status": "no_token"}

        info = {
            "status": "valid" if self.credentials.valid else "invalid",
            "expired": self.credentials.expired,
            "has_refresh_token": bool(self.credentials.refresh_token),
            "scopes": self.credentials.scopes,
        }

        if self.credentials.expiry:
            time_until = (self.credentials.expiry - datetime.now(timezone.utc)).total_seconds()
            info["expires_in_seconds"] = int(time_until)
            info["expires_at"] = self.credentials.expiry.isoformat()

        return info


# Singleton instance
token_manager = TokenManager()


if __name__ == "__main__":
    # CLI for token management
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python token_manager.py [auth|info|revoke]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    manager = TokenManager()
    
    if cmd == "auth":
        print("Starting Gmail OAuth2 authentication...")
        creds = manager.authenticate_interactive()
        if creds:
            print("Authentication successful!")
        else:
            print("Authentication failed!")
            sys.exit(1)
    
    elif cmd == "info":
        manager.load_credentials()
        info = manager.get_token_info()
        print(json.dumps(info, indent=2))
    
    elif cmd == "revoke":
        manager.load_credentials()
        if manager.revoke():
            print("Token revoked successfully")
        else:
            print("Failed to revoke token")
            sys.exit(1)
    
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python token_manager.py [auth|info|revoke]")
        sys.exit(1)
