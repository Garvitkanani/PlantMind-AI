"""
PDF Parser
Extracts text from PDF attachments with comprehensive error handling
"""

import logging
import os
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class PDFParser:
    """
    Parser for extracting text from PDF attachments
    Uses PyMuPDF (fitz) for efficient PDF processing
    """

    def __init__(self):
        self.supported_mimetypes = [
            "application/pdf",
            "application/x-pdf",
        ]

    def extract_text(self, pdf_path: str) -> str:
        """
        Extract text from a PDF file
        Returns the complete text content
        """
        text = ""

        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found: {pdf_path}")
            return ""

        try:
            import fitz

            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            logger.info(f"Processing PDF with {total_pages} pages: {pdf_path}")

            for page_num in range(total_pages):
                try:
                    page = doc.load_page(page_num)
                    page_text = page.get_text()
                    if page_text:
                        text += f"\n--- Page {page_num + 1} ---\n{page_text}"
                except Exception as e:
                    logger.warning(f"Error extracting text from page {page_num + 1}: {e}")
                    continue

            doc.close()
            extracted_length = len(text)
            logger.info(f"Extracted {extracted_length} characters from PDF")
            return text.strip()

        except ImportError:
            logger.error("PyMuPDF (fitz) not installed. Install with: pip install pymupdf")
            return ""
        except Exception as e:
            logger.error(f"Error parsing PDF {pdf_path}: {e}")
            return ""

    def extract_text_from_bytes(self, pdf_bytes: bytes, max_size_mb: int = 50) -> str:
        """
        Extract text from PDF bytes (when file is not saved)
        Returns the complete text content
        
        Args:
            pdf_bytes: Raw PDF bytes
            max_size_mb: Maximum PDF size in MB (default 50)
        """
        text = ""

        if not pdf_bytes:
            logger.warning("Empty PDF bytes provided")
            return ""

        size_mb = len(pdf_bytes) / (1024 * 1024)
        if size_mb > max_size_mb:
            logger.warning(f"PDF size ({size_mb:.1f}MB) exceeds limit ({max_size_mb}MB)")
            return ""

        try:
            import fitz

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            total_pages = len(doc)
            logger.info(f"Processing PDF from bytes: {total_pages} pages, {size_mb:.2f}MB")

            for page_num in range(total_pages):
                try:
                    page = doc.load_page(page_num)
                    page_text = page.get_text()
                    if page_text:
                        text += f"\n--- Page {page_num + 1} ---\n{page_text}"
                except Exception as e:
                    logger.warning(f"Error extracting text from page {page_num + 1}: {e}")
                    continue

            doc.close()
            logger.info(f"Extracted {len(text)} characters from PDF bytes")
            return text.strip()

        except ImportError:
            logger.error("PyMuPDF not installed")
            return ""
        except Exception as e:
            logger.error(f"Error parsing PDF from bytes: {e}")
            return ""

    def extract_tables(self, pdf_path: str) -> List[List[List[str]]]:
        """
        Extract tables from PDF (if any exist)
        Returns list of tables, each table is a list of rows
        """
        tables = []

        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found: {pdf_path}")
            return []

        try:
            import fitz

            doc = fitz.open(pdf_path)

            for page_num in range(len(doc)):
                try:
                    page = doc.load_page(page_num)
                    tables_on_page = page.find_tables()

                    if tables_on_page:
                        for table in tables_on_page:
                            table_data = []
                            for row in table.extract():
                                if row:
                                    table_data.append([str(cell) if cell is not None else "" for cell in row])
                            if table_data:
                                tables.append(table_data)
                                logger.debug(f"Extracted table from page {page_num + 1} with {len(table_data)} rows")
                except Exception as e:
                    logger.warning(f"Error extracting tables from page {page_num + 1}: {e}")
                    continue

            doc.close()
            logger.info(f"Extracted {len(tables)} tables from PDF")
            return tables

        except ImportError:
            logger.error("PyMuPDF not installed")
            return []
        except Exception as e:
            logger.error(f"Error extracting tables from PDF: {e}")
            return []

    def get_pdf_info(self, pdf_path: str) -> Dict:
        """
        Get metadata information about the PDF
        """
        info = {}

        try:
            import fitz

            doc = fitz.open(pdf_path)
            info = doc.metadata
            info["page_count"] = len(doc)
            doc.close()
            return info

        except ImportError:
            return {}
        except Exception as e:
            print("❌ Error getting PDF info: " + str(e))
            return info

    def is_possible_order_pdf(self, text: str) -> bool:
        """
        Check if PDF text appears to contain order-related content
        """
        order_keywords = [
            "purchase order",
            "po #",
            "po no",
            "order no",
            "order date",
            "delivery date",
            "quantity",
            "product",
            "item",
            "supplier",
            "customer",
            "invoice",
            "proforma",
        ]

        text_lower = text.lower()
        keyword_count = sum(1 for keyword in order_keywords if keyword in text_lower)

        # If 3 or more order keywords found, likely an order document
        return keyword_count >= 3

    def parse_pdf_attachment(self, attachment: Dict, attachment_path: str) -> Dict:
        """
        Parse a PDF attachment and return extracted data with comprehensive metadata
        """
        result = {
            "filename": attachment.get("filename", ""),
            "mimetype": attachment.get("mimeType", ""),
            "text": "",
            "tables": [],
            "is_order_pdf": False,
            "pages": 0,
            "success": False,
            "error": None,
            "file_size_bytes": 0,
            "extraction_time_ms": 0,
        }

        import time
        start_time = time.time()

        try:
            if os.path.exists(attachment_path):
                result["file_size_bytes"] = os.path.getsize(attachment_path)

            text = self.extract_text(attachment_path)
            result["text"] = text

            try:
                import fitz
                with fitz.open(attachment_path) as doc:
                    result["pages"] = len(doc)
            except Exception:
                result["pages"] = 0

            if len(text) > 10000:
                result["tables"] = self.extract_tables(attachment_path)

            result["is_order_pdf"] = self.is_possible_order_pdf(text)
            result["success"] = bool(text)
            result["extraction_time_ms"] = int((time.time() - start_time) * 1000)

            logger.info(f"Parsed PDF {result['filename']}: {result['pages']} pages, "
                       f"{len(text)} chars, {len(result['tables'])} tables, "
                       f"order={result['is_order_pdf']}")

        except Exception as e:
            result["error"] = str(e)
            result["extraction_time_ms"] = int((time.time() - start_time) * 1000)
            logger.error(f"Failed to parse PDF attachment: {e}")

        return result


# Test function
def test_pdf_parser():
    """Test the PDF parser"""
    parser = PDFParser()

    print("🧪 Testing PDF Parser")
    print("=" * 50)

    # Test with a sample PDF (if exists)
    test_pdf_path = "tests/sample_order.pdf"

    if os.path.exists(test_pdf_path):
        print(f"\n📄 Parsing: {test_pdf_path}")

        # Extract text
        text = parser.extract_text(test_pdf_path)
        print(f"\n📊 Extracted text (first 200 chars):")
        print(text[:200] + "..." if len(text) > 200 else text)

        # Get PDF info
        info = parser.get_pdf_info(test_pdf_path)
        print(f"\n📝 PDF Info:")
        for key, value in info.items():
            print(f"   {key}: {value}")

        # Check if it's an order PDF
        is_order = parser.is_possible_order_pdf(text)
        print(f"\n✅ Order PDF: {is_order}")

    else:
        print(f"\nℹ️  No test PDF found at {test_pdf_path}")
        print("   Create a sample PDF to test parsing.")

    print("\n" + "=" * 50)
    print("✅ PDF Parser testing complete!")


if __name__ == "__main__":
    test_pdf_parser()
