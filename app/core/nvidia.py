# Directory: rag-openrouter/app/core/nvidia.py

"""
OpenAI-compatible client pointed at the NVIDIA API Catalog (build.nvidia.com).
Shared by the embedding and chat services.
"""

from openai import OpenAI
from .config import get_settings

settings = get_settings()


def create_nvidia_client() -> OpenAI:
    """Create an OpenAI SDK client that talks to integrate.api.nvidia.com."""
    return OpenAI(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
    )
