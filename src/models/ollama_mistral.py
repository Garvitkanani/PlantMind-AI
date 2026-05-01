"""
AI Extraction Model
Uses Ollama local model for structured order data extraction.
Default model is phi3:mini.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class OllamaMistral:
    """
    AI Agent using a local Ollama model for order data extraction
    Communicates with Ollama API for LLM inference
    """

    def __init__(self):
        self.api_url = os.environ.get(
            "OLLAMA_API_URL", "http://localhost:11434/api/generate"
        )
        self.base_url = self.api_url.rsplit("/api/", 1)[0] if "/api/" in self.api_url else "http://localhost:11434"
        self.model = os.environ.get("OLLAMA_MODEL", "phi3:mini")
        self.timeout_seconds = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "180"))

    def is_healthy(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            with httpx.Client() as client:
                resp = client.get(f"{self.base_url}/api/tags", timeout=5.0)
                return resp.status_code == 200
        except Exception:
            return False

    def ensure_model_available(self) -> bool:
        """Check if the configured model is available in Ollama."""
        try:
            with httpx.Client() as client:
                resp = client.get(f"{self.base_url}/api/tags", timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    return self.model in models
            return False
        except Exception:
            return False

    def generate_response(self, prompt: str, stream: bool = False) -> str:
        """
        Generate response from configured Ollama model
        """
        payload = {"model": self.model, "prompt": prompt, "stream": stream}
        if self._expects_json(prompt):
            payload["format"] = "json"

        try:
            with httpx.Client() as client:
                response = client.post(
                    self.api_url, json=payload, timeout=self.timeout_seconds
                )
                if response.status_code >= 400:
                    error_detail = response.text
                    try:
                        parsed = response.json()
                        if parsed.get("error"):
                            error_detail = parsed.get("error")
                    except Exception:
                        pass
                    raise RuntimeError(
                        f"Ollama HTTP {response.status_code}: {error_detail}"
                    )

                if stream:
                    # Handle streaming response
                    full_response = ""
                    for line in response.iter_lines():
                        if line:
                            json_response = json.loads(line)
                            if "response" in json_response:
                                full_response += json_response["response"]
                    return full_response
                else:
                    # Handle non-streaming response
                    result = response.json()
                    if result.get("error"):
                        raise RuntimeError(f"Ollama error: {result.get('error')}")
                    response_text = result.get("response", "")
                    if not response_text:
                        raise RuntimeError(f"Ollama empty response payload: {result}")
                    if self._expects_json(prompt):
                        return self._normalize_json_response(response_text)
                    return response_text

        except httpx.TimeoutException as e:
            raise RuntimeError(f"Ollama timeout after {self.timeout_seconds}s: {e}") from e
        except httpx.RequestError as e:
            raise RuntimeError(f"Ollama request error: {e}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Ollama response JSON decode error: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Ollama generation failed: {e}") from e

    def _expects_json(self, prompt: str) -> bool:
        prompt_lower = prompt.lower()
        return "json" in prompt_lower and "return" in prompt_lower

    def _normalize_json_response(self, response_text: str) -> str:
        """Normalize model JSON-ish output into strict JSON when possible."""
        cleaned = response_text.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^```\s*|\s*```$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"//.*?$", "", cleaned, flags=re.MULTILINE)

        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        candidate = match.group(0) if match else cleaned

        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                # Keep None values as-is — downstream validation depends on them
                return json.dumps(parsed)
        except Exception:
            return response_text

        return response_text

    def extract_order_data(self, email_text: str, attachment_text: str = "") -> Dict:
        """
        Extract order data from email and attachment text
        Returns structured order data dictionary
        """
        # Build prompt for structured extraction
        prompt = self._build_extraction_prompt(email_text, attachment_text)

        # Generate response
        response = self.generate_response(prompt)

        # Parse JSON from response
        order_data = self._parse_llm_response(response)

        return order_data

    def _build_extraction_prompt(self, email_text: str, attachment_text: str) -> str:
        """
        Build prompt for order data extraction
        """
        # Combine email and attachment text
        combined_text = f"EMAIL CONTENT:\n{email_text}\n\n"

        if attachment_text:
            combined_text += f"ATTACHMENT CONTENT:\n{attachment_text}\n\n"

        # Add instructions for structured output
        prompt = f"""You are an order processing assistant. Extract order information from the email and attachment content below.

Please extract the following fields:
1. customer_name - Name of the customer placing the order
2. customer_email - Email address of the customer
3. product_name - Name of the product being ordered
4. quantity - Number of units ordered (as integer)
5. delivery_date - Requested delivery date (format: YYYY-MM-DD)
6. special_instructions - Any special notes or requirements

{combined_text}

Return your response as a valid JSON object with the exact keys specified above. Do not include any additional text or explanations.

JSON Response:"""

        return prompt

    def _parse_llm_response(self, response: str) -> Dict:
        """
        Parse AI response and extract JSON order data
        """
        order_data = {
            "customer_name": "",
            "customer_email": "",
            "product_name": "",
            "quantity": 0,
            "delivery_date": "",
            "special_instructions": "",
            "valid": False,
            "extraction_confidence": 0.0,
            "error": None,
        }

        try:
            # Try to find JSON in the response
            json_match = re.search(r"\{[^{}]+\}", response, re.DOTALL)

            if json_match:
                json_str = json_match.group(0)
                parsed_data = json.loads(json_str)

                # Validate required fields
                required_fields = [
                    "customer_name",
                    "customer_email",
                    "product_name",
                    "quantity",
                ]

                missing_fields = [
                    field for field in required_fields if not parsed_data.get(field)
                ]

                # Map parsed data to order_data
                order_data["customer_name"] = parsed_data.get("customer_name", "")
                order_data["customer_email"] = parsed_data.get("customer_email", "")
                order_data["product_name"] = parsed_data.get("product_name", "")
                order_data["quantity"] = int(parsed_data.get("quantity", 0))
                order_data["delivery_date"] = parsed_data.get("delivery_date", "")
                order_data["special_instructions"] = parsed_data.get(
                    "special_instructions", ""
                )

                # Set validity based on required fields
                order_data["valid"] = len(missing_fields) == 0

                if missing_fields:
                    order_data["error"] = (
                        f"Missing required fields: {', '.join(missing_fields)}"
                    )

            else:
                order_data["error"] = "No valid JSON found in response"

        except json.JSONDecodeError as e:
            order_data["error"] = f"JSON parse error: {e}"
        except Exception as e:
            order_data["error"] = f"Extraction error: {e}"

        return order_data

    def validate_order_data(self, order_data: Dict) -> Dict:
        """
        Validate extracted order data
        Returns validation result
        """
        validation_result = {"valid": False, "errors": [], "warnings": []}

        # Check required fields
        if not order_data.get("customer_name"):
            validation_result["errors"].append("Customer name is required")

        if not order_data.get("customer_email"):
            validation_result["errors"].append("Customer email is required")

        if not order_data.get("product_name"):
            validation_result["errors"].append("Product name is required")

        if not order_data.get("quantity") or order_data.get("quantity", 0) <= 0:
            validation_result["errors"].append("Valid quantity is required")

        # Validate email format
        if order_data.get("customer_email"):
            email = order_data["customer_email"]
            if "@" not in email or "." not in email:
                validation_result["warnings"].append("Email format may be invalid")

        # Validate date format if present
        if order_data.get("delivery_date"):
            date_str = order_data["delivery_date"]
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                validation_result["warnings"].append(
                    "Delivery date should be in YYYY-MM-DD format"
                )

        validation_result["valid"] = len(validation_result["errors"]) == 0

        return validation_result


# Test function
def test_ollama_extraction():
    """Test the AI extraction"""
    import os

    # Check if Ollama is running
    print("🧪 Testing AI Extractor\n" + "=" * 50)

    # Sample email text for testing
    sample_email = """
    From: rajesh@rajeshpolymers.com
    Subject: Purchase Order for HDPE Caps

    Hello,

    We would like to place an order for the following product:

    Product: HDPE Cap 50mm
    Quantity: 5000 units
    Delivery Date: 2025-06-15
    Special Instructions: Please ensure the caps are food-grade certified.

    regards,
    Rajesh Polymers
    orders@rajesh.com
    """

    sample_attachment = """
    Purchase Order #PO-2024-001
    ===========================

    Customer: Rajesh Polymers
    Order Date: 2024-01-15

    Items Ordered:
    1. HDPE Cap 50mm - 5000 units @ $0.05/unit
    2. Delivery by June 15, 2025

    Special Notes: Food-grade certification required.
    """

    extractor = OllamaMistral()

    print("\n📤 Sending request to Ollama...")
    print(f"   API URL: {extractor.api_url}")
    print(f"   Model: {extractor.model}")
    print()

    try:
        order_data = extractor.extract_order_data(sample_email, sample_attachment)

        print("📝 Extracted Order Data:")
        for key, value in order_data.items():
            print(f"   {key}: {value}")

        # Test validation
        validation = extractor.validate_order_data(order_data)
        print(f"\n✅ Validation Result: {validation}")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Note: Make sure Ollama is running with phi3:mini model.")
        print("   Run: ollama pull phi3:mini")

    print("\n" + "=" * 50)
    print("✅ AI Extraction testing complete!")


if __name__ == "__main__":
    test_ollama_extraction()
