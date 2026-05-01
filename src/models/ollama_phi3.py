"""
Phi-3 Mini AI Model — Email & Communication Drafting Engine
Uses Ollama local model (Phi-3 Mini Q4_K_M) for generating professional emails:
  - Supplier reorder requests
  - Customer dispatch confirmations
  - Production delay alerts to owner
  - General professional communications

Phi-3 Mini is chosen for these tasks because:
  - Lightweight (< 4 GB RAM) — can run alongside Mistral 7B
  - Fast inference (~2-5s per generation)
  - Strong instruction-following for structured text output
  - Ideal for formulaic but professional writing
"""

import json
import logging
import os
import re
import time
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class OllamaPhi3:
    """
    AI Agent using a local Ollama Phi-3 Mini model for drafting professional emails.
    Communicates with the Ollama REST API for LLM inference.
    """

    def __init__(self):
        self.api_url = os.environ.get(
            "OLLAMA_API_URL", "http://localhost:11434/api/generate"
        )
        self.base_url = self.api_url.rsplit("/api/", 1)[0] if "/api/" in self.api_url else "http://localhost:11434"
        self.model = os.environ.get("OLLAMA_PHI3_MODEL", "phi3:mini")
        self.timeout_seconds = float(
            os.environ.get("OLLAMA_PHI3_TIMEOUT_SECONDS", "120")
        )
        self.max_retries = int(os.environ.get("OLLAMA_PHI3_MAX_RETRIES", "2"))

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

    # ------------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------------

    def generate_response(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False,
    ) -> str:
        """
        Generate a text response from Phi-3 Mini.

        Args:
            prompt: The instruction / system prompt
            temperature: Creativity dial (0.0 = deterministic, 1.0 = creative)
            max_tokens: Upper bound on generated tokens
            stream: Whether to use streaming mode

        Returns:
            The generated text string
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client() as client:
                    response = client.post(
                        self.api_url,
                        json=payload,
                        timeout=self.timeout_seconds,
                    )

                    if response.status_code >= 400:
                        error_detail = response.text
                        try:
                            parsed = response.json()
                            if parsed.get("error"):
                                error_detail = parsed["error"]
                        except Exception:
                            pass
                        raise RuntimeError(
                            f"Ollama HTTP {response.status_code}: {error_detail}"
                        )

                    if stream:
                        full_response = ""
                        for line in response.iter_lines():
                            if line:
                                json_response = json.loads(line)
                                if "response" in json_response:
                                    full_response += json_response["response"]
                        return full_response.strip()
                    else:
                        result = response.json()
                        if result.get("error"):
                            raise RuntimeError(
                                f"Ollama error: {result['error']}"
                            )
                        response_text = result.get("response", "")
                        if not response_text:
                            raise RuntimeError(
                                f"Ollama empty response payload: {result}"
                            )
                        return self._clean_response(response_text)

            except httpx.TimeoutException as e:
                last_error = RuntimeError(
                    f"Ollama Phi-3 timeout after {self.timeout_seconds}s (attempt {attempt}): {e}"
                )
                logger.warning(str(last_error))
            except httpx.RequestError as e:
                last_error = RuntimeError(
                    f"Ollama Phi-3 request error (attempt {attempt}): {e}"
                )
                logger.warning(str(last_error))
            except json.JSONDecodeError as e:
                last_error = RuntimeError(
                    f"Ollama Phi-3 JSON decode error (attempt {attempt}): {e}"
                )
                logger.warning(str(last_error))
            except RuntimeError as e:
                last_error = e
                logger.warning(str(e))

            if attempt < self.max_retries:
                backoff = 2 ** (attempt - 1)
                logger.info(f"Retrying Phi-3 in {backoff}s...")
                time.sleep(backoff)

        raise last_error or RuntimeError("Phi-3 generation failed after all retries")

    # ------------------------------------------------------------------
    # Email drafting helpers
    # ------------------------------------------------------------------

    def draft_reorder_email(
        self,
        material_name: str,
        quantity_kg: float,
        supplier_name: str,
        current_stock_kg: float = 0,
        reorder_level_kg: float = 0,
        factory_name: str = "PlantMind AI Factory",
    ) -> tuple[str, str]:
        """
        Draft a professional reorder email to a supplier.

        Returns:
            Tuple of (subject, body)
        """
        prompt = f"""You are the procurement officer at {factory_name}, a plastic injection moulding factory.
Draft a professional email to reorder raw materials from a supplier.

Details:
- Material: {material_name}
- Quantity to order: {quantity_kg} kg
- Supplier: {supplier_name}
- Current stock: {current_stock_kg} kg
- Reorder level: {reorder_level_kg} kg (stock is below this threshold)

Requirements:
1. Write a clear subject line first, then the body
2. Be professional, concise, and clear
3. Include material name and exact quantity
4. Request confirmation of availability and expected delivery date
5. Include a polite closing with {factory_name} Procurement Team
6. Keep the body under 150 words

Format your response EXACTLY as:
SUBJECT: [subject line]

BODY:
[email body]"""

        try:
            response = self.generate_response(prompt, temperature=0.6)
            subject, body = self._parse_subject_body(response)

            if not subject:
                subject = f"Purchase Order: {material_name} — {quantity_kg} kg"

            return subject, body

        except Exception as e:
            logger.error(f"Phi-3 reorder email drafting failed: {e}")
            return self._fallback_reorder_email(
                material_name, quantity_kg, supplier_name, factory_name
            )

    def draft_dispatch_email(
        self,
        customer_name: str,
        order_id: int,
        product_name: str,
        quantity: int,
        factory_name: str = "PlantMind AI Factory",
    ) -> str:
        """
        Draft a professional dispatch confirmation email body.

        Returns:
            Email body text
        """
        prompt = f"""You are the dispatch coordinator at {factory_name}, a plastic injection moulding factory.
Write a professional dispatch confirmation email to a customer.

Details:
- Customer: {customer_name}
- Order ID: #{order_id}
- Product: {product_name}
- Quantity: {quantity:,} units
- Status: Ready for dispatch

Requirements:
1. Address the customer by name
2. Confirm their order is complete and ready for dispatch
3. Include the order ID, product name, and quantity
4. Ask them to coordinate pickup/delivery logistics
5. Include a warm, professional closing
6. Keep the body between 80-120 words
7. Do NOT include a subject line — write ONLY the email body

Write the email body now:"""

        try:
            body = self.generate_response(prompt, temperature=0.7)
            body = self._strip_subject_if_present(body)

            # Quality gate: body should be at least 50 characters
            if len(body) < 50:
                raise ValueError("Generated body too short")

            return body

        except Exception as e:
            logger.error(f"Phi-3 dispatch email drafting failed: {e}")
            return self._fallback_dispatch_email(
                customer_name, order_id, product_name, quantity, factory_name
            )

    def draft_delay_alert(
        self,
        order_id: int,
        customer_name: str,
        product_name: str,
        pieces_completed: int,
        total_pieces: int,
        original_deadline: str,
        new_eta: str,
        factory_name: str = "PlantMind AI Factory",
    ) -> str:
        """
        Draft an urgent but professional delay alert email body for the owner.

        Returns:
            Email body text
        """
        completion_pct = (
            (pieces_completed / total_pieces * 100) if total_pieces > 0 else 0
        )

        prompt = f"""You are the production manager at {factory_name}.
Write an urgent but professional email to the factory owner about a production delay.

Delay Details:
- Order ID: #{order_id}
- Customer: {customer_name}
- Product: {product_name}
- Original Deadline: {original_deadline}
- New Estimated Completion: {new_eta}
- Progress: {pieces_completed:,} / {total_pieces:,} pieces ({completion_pct:.1f}%)

Requirements:
1. Clearly state the delay with specific numbers
2. Explain current progress percentage and pace
3. Suggest concrete next steps: contact customer, expedite production, allocate additional resources
4. Be professional but convey urgency — this is a production problem
5. Keep the body between 100-150 words
6. Do NOT include a subject line — write ONLY the email body

Write the alert email body now:"""

        try:
            body = self.generate_response(prompt, temperature=0.5)
            body = self._strip_subject_if_present(body)

            if len(body) < 50:
                raise ValueError("Generated body too short")

            return body

        except Exception as e:
            logger.error(f"Phi-3 delay alert drafting failed: {e}")
            return self._fallback_delay_alert(
                order_id,
                customer_name,
                product_name,
                pieces_completed,
                total_pieces,
                original_deadline,
                new_eta,
                factory_name,
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _clean_response(self, text: str) -> str:
        """Strip markdown code fences and extra whitespace."""
        cleaned = text.strip()
        # Remove ```...``` wrapping
        cleaned = re.sub(r"^```(?:\w+)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    def _parse_subject_body(self, response: str) -> tuple[str, str]:
        """Parse a response that contains SUBJECT: and BODY: markers."""
        subject = ""
        body = response.strip()

        if "SUBJECT:" in response.upper():
            # Case-insensitive split on BODY:
            body_split = re.split(r"BODY:\s*", response, maxsplit=1, flags=re.IGNORECASE)
            if len(body_split) == 2:
                subject_part = body_split[0].strip()
                body = body_split[1].strip()

                subject_match = re.search(
                    r"SUBJECT:\s*(.+)", subject_part, flags=re.IGNORECASE
                )
                if subject_match:
                    subject = subject_match.group(1).strip()

        return subject, body

    def _strip_subject_if_present(self, text: str) -> str:
        """If the model accidentally includes a subject line, remove it."""
        lines = text.strip().split("\n")
        # Check if first line looks like a subject
        if lines and re.match(r"^(Subject|SUBJECT|Re):\s", lines[0]):
            return "\n".join(lines[1:]).strip()
        return text.strip()

    # ------------------------------------------------------------------
    # Fallback templates (when Ollama is unavailable)
    # ------------------------------------------------------------------

    def _fallback_reorder_email(
        self,
        material_name: str,
        quantity_kg: float,
        supplier_name: str,
        factory_name: str,
    ) -> tuple[str, str]:
        """Deterministic fallback when AI is unavailable."""
        subject = f"Purchase Order: {material_name} — {quantity_kg} kg"
        body = f"""Dear {supplier_name},

We would like to place an order for the following raw material:

Material: {material_name}
Quantity Required: {quantity_kg} kg

Our current stock has fallen below our minimum threshold, and we require prompt replenishment to maintain our production schedule.

Please confirm availability and provide your expected delivery timeline at your earliest convenience.

Best regards,
{factory_name} Procurement Team"""

        return subject, body

    def _fallback_dispatch_email(
        self,
        customer_name: str,
        order_id: int,
        product_name: str,
        quantity: int,
        factory_name: str,
    ) -> str:
        """Deterministic fallback for dispatch email."""
        return f"""Dear {customer_name},

We are pleased to inform you that your order has been completed and is ready for dispatch.

Order Details:
  Order ID: #{order_id}
  Product: {product_name}
  Quantity: {quantity:,} units

Please contact us at your convenience to arrange pickup or delivery logistics. We will ensure your order is packaged and ready for transport.

Thank you for your business.

Warm regards,
{factory_name} Dispatch Team"""

    def _fallback_delay_alert(
        self,
        order_id: int,
        customer_name: str,
        product_name: str,
        pieces_completed: int,
        total_pieces: int,
        original_deadline: str,
        new_eta: str,
        factory_name: str,
    ) -> str:
        """Deterministic fallback for delay alert."""
        pct = (pieces_completed / total_pieces * 100) if total_pieces > 0 else 0
        return f"""Dear Owner,

URGENT: A production delay has been detected for Order #{order_id}.

Customer: {customer_name}
Product: {product_name}
Progress: {pieces_completed:,} / {total_pieces:,} pieces ({pct:.1f}%)

Original Deadline: {original_deadline}
New Estimated Completion: {new_eta}

The current production pace indicates we will not meet the original delivery commitment. Recommended actions:

1. Contact {customer_name} to communicate the revised timeline
2. Evaluate whether additional shifts or machine allocation can accelerate production
3. Review material availability to ensure no supply bottlenecks

Please review and advise on next steps.

Best regards,
{factory_name} Production Management System"""


# ------------------------------------------------------------------
# Singleton instance for convenience
# ------------------------------------------------------------------
ollama_phi3 = OllamaPhi3()
