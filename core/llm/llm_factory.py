"""
LLM Factory - Creates LLM clients based on provider type
"""
import logging
from typing import Optional
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
import config

logger = logging.getLogger(__name__)

class LLMFactory:
    """Factory for creating LLM provider instances"""
    
    @staticmethod
    def create_llm_client(
        provider: str,
        model: str,
        api_key: Optional[str] = None
    ):
        """
        Create an LLM client based on provider type
        
        Args:
            provider: 'openai' or 'gemini'
            model: Model name (e.g., 'gpt-4o', 'gemini-pro')
            api_key: API key (if None, uses config defaults)
        
        Returns:
            LLM provider instance
        """
        provider = provider.lower()
        
        if provider == 'openai':
            if api_key is None:
                api_key = getattr(config, 'OPENAI_API_KEY', None)
            if not api_key:
                raise ValueError("OpenAI API key is required")
            return OpenAIProvider(api_key=api_key, model=model)
        
        elif provider == 'gemini':
            if api_key is None:
                api_key = getattr(config, 'GEMINI_API_KEY', None)
            if not api_key:
                raise ValueError("Gemini API key is required")
            return GeminiProvider(api_key=api_key, model=model)
        
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

