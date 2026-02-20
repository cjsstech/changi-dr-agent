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
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None
    ) -> str | dict:
        """Generate chat completion"""
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            if tools:
                # Format to OpenAI's expected structure
                openai_tools = [{"type": "function", "function": tool} for tool in tools]
                kwargs["tools"] = openai_tools

            response = self.client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            
            # Check for tool call
            if getattr(message, 'tool_calls', None) and len(message.tool_calls) > 0:
                tool_call = message.tool_calls[0]
                import json
                try:
                    args_dict = json.loads(tool_call.function.arguments)
                except:
                    args_dict = {}
                return {
                    "function_call": {
                        "name": tool_call.function.name,
                        "arguments": args_dict
                    }
                }
            
            return message.content.strip() if message.content else ""
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

