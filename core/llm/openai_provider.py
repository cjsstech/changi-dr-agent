"""
OpenAI LLM Provider
"""
import logging
import httpx
from openai import OpenAI
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class OpenAIProvider:
    """OpenAI LLM provider implementation"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
        # Disable SSL verification for corporate networks with SSL inspection
        http_client = httpx.Client(verify=False)
        self.client = OpenAI(api_key=api_key, http_client=http_client)
        logger.info(f"Initialized OpenAI provider with model: {model}")
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate chat completion"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

