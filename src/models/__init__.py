"""
Models Package
Contains AI models and extraction logic
  - OllamaMistral: Mistral 7B for order extraction and MIS report generation
  - OllamaPhi3: Phi-3 Mini for email drafting (reorder, dispatch, delay alerts)
"""

from .ollama_mistral import OllamaMistral
from .ollama_phi3 import OllamaPhi3

__all__ = ["OllamaMistral", "OllamaPhi3"]
