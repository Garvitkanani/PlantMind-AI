"""
Attachment Parser - Routing Layer
Matches V1 specification: Routes to PDF or DOCX parser, handles unsupported formats
"""

import logging
import os
import re
import tempfile
from typing import Optional, Tuple

from .docx_parser import DOCXParser
from .pdf_parser import PDFParser

logger = logging.getLogger(__name__)


def _sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks.
    Removes any path components and special characters.
    """
    if not filename:
        return "unnamed"
    # Get basename only (remove any path components)
    basename = os.path.basename(filename)
    # Remove any non-alphanumeric characters except safe ones
    sanitized = re.sub(r'[^\w\s.-]', '', basename)
    # Limit length
    if len(sanitized) > 100:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:100] + ext
    return sanitized or "unnamed"


class AttachmentParser:
    """
    Attachment Parser Agent - Routes to PDF or DOCX parser
    Responsibility:
    - Receive list of attachments from email
    - Download each attachment temporarily
    - Extract all readable text from PDF or DOCX
    - Return combined plain text
    - Delete temporary files after extraction
    """

    def __init__(self):
        self.pdf_parser = PDFParser()
        self.docx_parser = DOCXParser()

    def extract_all_text(
        self, attachments: list, email_body: str = ""
    ) -> Tuple[str, list]:
        """
        Extract text from all attachments and combine with email body

        Args:
            attachments: List of attachment objects with 'filename' and 'data' keys
            email_body: Original email body text

        Returns:
            Tuple of (combined_text, attachment_info_list)
        """
        combined_text = email_body
        attachment_info = []

        if not attachments:
            return combined_text, attachment_info

        for i, attachment in enumerate(attachments):
            filename = _sanitize_filename(attachment.get("filename", f"attachment_{i}"))
            data = attachment.get("data")

            if not data:
                continue

            # Create temporary file
            temp_file = None
            try:
                # Determine file type from extension
                ext = os.path.splitext(filename)[1].lower()

                # Create temp file
                with tempfile.NamedTemporaryFile(
                    suffix=ext, delete=False, mode="wb"
                ) as f:
                    f.write(data)
                    temp_file = f.name

                # Extract text based on file type
                if ext == ".pdf":
                    text = self.pdf_parser.extract_text_from_bytes(data)
                    attachment_type = "pdf"
                elif ext == ".docx":
                    text = self.docx_parser.extract_text_from_bytes(data)
                    attachment_type = "docx"
                elif ext == ".doc":
                    # DOC format not supported - log warning but continue
                    logger.warning(".doc format not supported for %s", filename)
                    text = ""
                    attachment_type = "unsupported_doc"
                else:
                    logger.warning("Unsupported file type %s for %s", ext, filename)
                    text = ""
                    attachment_type = "unsupported"

                # Append to combined text
                if text:
                    combined_text += (
                        f"\n\n--- Attachment {filename} ({attachment_type}) ---\n{text}"
                    )

                attachment_info.append(
                    {
                        "filename": filename,
                        "type": attachment_type,
                        "text": text,
                        "success": bool(text),
                    }
                )

            except Exception as e:
                logger.error("Error processing attachment %s: %s", filename, e)
                attachment_info.append(
                    {
                        "filename": filename,
                        "type": "error",
                        "error": str(e),
                        "success": False,
                    }
                )
            finally:
                # Clean up temp file
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except OSError:
                        # Best-effort cleanup; parsing result is already computed.
                        pass

        return combined_text, attachment_info

    def parse_attachment(self, attachment_data: bytes, filename: str) -> Optional[str]:
        """
        Parse a single attachment

        Args:
            attachment_data: Raw attachment data
            filename: Original filename

        Returns:
            Extracted text or None if unsupported/error
        """
        filename = _sanitize_filename(filename)
        ext = os.path.splitext(filename)[1].lower()

        # Create temporary file
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False, mode="wb") as f:
                f.write(attachment_data)
                temp_file = f.name

            if ext == ".pdf":
                return self.pdf_parser.extract_text(temp_file)
            elif ext == ".docx":
                return self.docx_parser.extract_text(temp_file)
            else:
                logger.warning("Unsupported file type: %s", ext)
                return None

        except Exception as e:
            logger.error("Error parsing attachment: %s", e)
            return None
        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except OSError:
                    # Best-effort cleanup; parsing result is already computed.
                    pass


# Singleton instance
attachment_parser = AttachmentParser()
