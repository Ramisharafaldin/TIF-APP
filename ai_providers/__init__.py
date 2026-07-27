"""
AI Providers package (Phase 3, §4).

Public surface:
  - AIProviderInterface        (base interface)
  - AIResponse                 (provider-agnostic response)
  - get_provider(name, **kw)   (factory: resolve a provider class by name)
  - PROVIDER_REGISTRY          (name -> class mapping)
"""

from ai_providers.base import AIProviderInterface, AIResponse
from ai_providers.gemini_provider import GeminiProvider
from ai_providers.openai_provider import OpenAIProvider
from ai_providers.openrouter_provider import OpenRouterProvider
from ai_providers.lmstudio_provider import LMStudioProvider
from ai_providers.azure_openai_provider import AzureOpenAIProvider
from ai_providers.custom_provider import CustomProvider
from ai_providers.ollama_provider import OllamaProvider

PROVIDER_REGISTRY = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
    "openrouter": OpenRouterProvider,
    "lmstudio": LMStudioProvider,
    "azure_openai": AzureOpenAIProvider,
    "custom": CustomProvider,
    "ollama": OllamaProvider,
}


def get_provider(name: str = None, **kwargs):
    """
    Resolve and instantiate a provider by its short name.

    Args:
        name: One of PROVIDER_REGISTRY keys (e.g. 'gemini', 'ollama').
               If None/unknown, falls back to 'gemini' for backward compat.
        **kwargs: Forwarded to the provider constructor (model, api_key, ...).
    """
    name = (name or "gemini").lower()
    cls = PROVIDER_REGISTRY.get(name)
    if cls is None:
        logger_warning(f"Unknown AI provider '{name}', falling back to gemini")
        cls = GeminiProvider
        name = "gemini"
    return cls(**kwargs)


def logger_warning(msg: str):
    import logging
    logging.getLogger(__name__).warning(msg)


__all__ = [
    "AIProviderInterface", "AIResponse", "PROVIDER_REGISTRY", "get_provider",
    "GeminiProvider", "OpenAIProvider", "OpenRouterProvider", "LMStudioProvider",
    "AzureOpenAIProvider", "CustomProvider", "OllamaProvider",
]
