"""
Order Extraction Agent
Uses configured Ollama model to extract structured order data from emails.
Supports retry on transient failures and few-shot prompting for accuracy.
"""

import json
import logging
import re
from typing import Dict, List, Optional

from src.models.ollama_mistral import OllamaMistral

logger = logging.getLogger(__name__)


MAX_RETRIES = 2


class OrderExtractionAgent:
    """
    Order Extraction Agent
    Responsibility:
    - Combine email body text + attachment text into one string
    - Send to configured local Ollama model via API
    - Parse AI response as JSON
    - Validate all required fields are present
    - Return structured order data or flag as incomplete
    """

    def __init__(self):
        self.mistral_model = OllamaMistral()
        self.required_fields = [
            "customer_name",
            "customer_email",
            "product_name",
            "quantity",
            "delivery_date",
            "special_instructions",
        ]
        self.extraction_prompt = self._get_extraction_prompt()

    def _get_extraction_prompt(self) -> str:
        """Few-shot extraction prompt for maximum accuracy with local models"""
        return """You are an order processing assistant for a plastic injection moulding factory.
You will receive the content of a customer email and any attached Purchase Order.

Extract these fields and return ONLY a valid JSON object — no explanation, no extra text.

Fields to extract:
- customer_name: Company or person placing the order
- customer_email: Email address of the sender
- product_name: Product or part being ordered
- quantity: Number of units (integer only)
- delivery_date: Required delivery date (YYYY-MM-DD format)
- special_instructions: Any special notes (empty string if none)

If a field cannot be determined, set its value to null.

Example output:
{{"customer_name":"Rajesh Polymers","customer_email":"orders@rajesh.com","product_name":"HDPE Cap 50mm","quantity":5000,"delivery_date":"2025-06-15","special_instructions":"Food-grade certified"}}

Now extract from this content:
{content}

JSON:"""

    def extract_order(self, email_content: str, sender_email: str) -> Dict:
        """
        Extract structured order data from combined email content

        Args:
            email_content: Combined email body + attachment text
            sender_email: Sender's email address (used as fallback)

        Returns:
            Dictionary with extracted data and metadata
        """
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                full_prompt = self.extraction_prompt.format(content=email_content)

                logger.info("Sending content to Ollama model (attempt %d)...", attempt)
                ai_response = self.mistral_model.generate_response(full_prompt)

                if not ai_response:
                    raise ValueError("Empty response from AI model")

                extracted_data = self._parse_ai_response(ai_response, sender_email)
                is_complete, missing_fields = self._validate_extraction(extracted_data)

                result = {
                    "extracted_data": extracted_data,
                    "is_complete": is_complete,
                    "missing_fields": missing_fields,
                    "sender_email": sender_email,
                    "error": None,
                }

                logger.info(
                    "Extraction completed (attempt %d). Complete: %s, Missing: %s",
                    attempt, is_complete, missing_fields,
                )
                return result

            except RuntimeError as e:
                last_error = e
                logger.warning("Extraction attempt %d failed: %s", attempt, e)
                # Treat explicit extraction pipeline errors as hard failures.
                if "extraction error" in str(e).lower():
                    break
                if attempt < MAX_RETRIES:
                    continue
                break
            except Exception as e:
                last_error = e
                logger.warning("Extraction attempt %d failed: %s", attempt, e)
                if attempt < MAX_RETRIES:
                    continue

        # All retries exhausted
        error_msg = f"Order extraction failed after {MAX_RETRIES} attempts: {last_error}"
        logger.error(error_msg)
        return {
            "extracted_data": {},
            "is_complete": False,
            "missing_fields": self.required_fields,
            "sender_email": sender_email,
            "error": error_msg,
        }

    def _clean_json_response(self, response: str) -> str:
        """
        Clean up common LLM JSON formatting issues.
        phi3:mini sometimes produces escaped underscores (customer\\_name).
        """
        cleaned = response
        
        # Fix escaped underscores (customer\_name -> customer_name)
        cleaned = cleaned.replace('\\_', '_')
        
        # Fix escaped backslashes (\\ -> \)
        cleaned = cleaned.replace('\\\\', '\\')
        
        # Remove markdown code block markers if present
        cleaned = re.sub(r'^```json\s*', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'```\s*$', '', cleaned, flags=re.MULTILINE)
        
        return cleaned

    def _parse_ai_response(self, ai_response: str, sender_email: str) -> Dict:
        """Parse AI response JSON and clean up data"""
        # Clean up common LLM JSON formatting issues
        cleaned_response = self._clean_json_response(ai_response)
        
        # Try to extract and parse JSON
        data = None
        parse_error = None
        
        try:
            # Try direct parsing first
            data = json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            parse_error = e
            # Try to extract JSON from response
            try:
                json_match = re.search(r"\{.*\}", cleaned_response, re.DOTALL)
                if json_match:
                    extracted_json = self._clean_json_response(json_match.group())
                    data = json.loads(extracted_json)
                else:
                    raise ValueError(f"Invalid JSON response: {str(e)}")
            except Exception as inner_e:
                if isinstance(inner_e, ValueError):
                    raise inner_e
                raise ValueError(f"Invalid JSON response: {str(e)}")
        
        # Process the extracted data
        cleaned_data = {}

        # Map fields with defaults
        cleaned_data["customer_name"] = data.get("customer_name")

        # Use sender_email as fallback for customer_email
        cleaned_data["customer_email"] = data.get("customer_email", sender_email)
        if not cleaned_data["customer_email"]:
            cleaned_data["customer_email"] = sender_email

        cleaned_data["product_name"] = data.get("product_name")

        # Clean quantity - ensure it's an integer
        quantity_value = data.get("quantity")
        if quantity_value:
            try:
                # Handle formats like "10,000 pieces" robustly.
                normalized = str(quantity_value).replace(",", "")
                
                # Check for negative value - reject immediately
                if "-" in normalized and normalized.strip().startswith("-"):
                    cleaned_data["quantity"] = None
                else:
                    match = re.search(r"\d+", normalized)
                    if match:
                        cleaned_data["quantity"] = int(match.group())
                    else:
                        cleaned_data["quantity"] = int(normalized)
            except (ValueError, TypeError):
                cleaned_data["quantity"] = None
        else:
            cleaned_data["quantity"] = None

        cleaned_data["delivery_date"] = data.get("delivery_date")

        # Ensure special_instructions is string
        special_instructions = data.get("special_instructions")
        if special_instructions is None:
            cleaned_data["special_instructions"] = ""
        else:
            cleaned_data["special_instructions"] = str(special_instructions)

        return cleaned_data

    def _validate_extraction(self, extracted_data: Dict) -> tuple:
        """
        Validate that all required fields are present and valid

        Args:
            extracted_data: Dictionary of extracted fields

        Returns:
            Tuple of (is_complete, missing_fields)
        """
        missing_fields = []

        for field in [
            "customer_name",
            "customer_email",
            "product_name",
            "quantity",
            "delivery_date",
        ]:
            value = extracted_data.get(field)

            if value is None or (isinstance(value, str) and not value.strip()):
                missing_fields.append(field)
            elif field == "quantity" and (not isinstance(value, int) or value <= 0):
                missing_fields.append(field)
            elif field == "delivery_date" and not self._is_valid_date(value):
                missing_fields.append(field)

        is_complete = len(missing_fields) == 0

        return is_complete, missing_fields

    def _is_valid_date(self, date_str: str | None) -> bool:
        """Check if date string is valid YYYY-MM-DD format"""
        try:
            if not date_str:
                return False

            # Check format
            import re

            if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                return False

            # Parse date
            from datetime import datetime

            datetime.strptime(date_str, "%Y-%m-%d")
            return True

        except ValueError:
            return False


# Singleton instance
order_extractor = OrderExtractionAgent()
