"""
Google Gemini LLM Provider
"""
import logging
from typing import List, Dict, Optional, Generator

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not installed. Gemini provider unavailable.")

class GeminiProvider:
    """Google Gemini LLM provider implementation"""
    
    def __init__(self, api_key: str, model: str = "gemini-pro"):
        if not GEMINI_AVAILABLE:
            raise ImportError("google-generativeai package is required for Gemini provider")
        
        self.api_key = api_key
        self.model = model
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)
        logger.info(f"Initialized Gemini provider with model: {model}")
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None
    ) -> str | dict:
        """Generate chat completion"""
        try:
            # Convert messages format for Gemini
            # Gemini uses a different format - combine system and user messages
            prompt_parts = []
            for msg in messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                if role == 'system':
                    prompt_parts.append(f"System: {content}")
                elif role == 'user':
                    prompt_parts.append(f"User: {content}")
                elif role == 'assistant':
                    prompt_parts.append(f"Assistant: {content}")
            
            prompt = "\n".join(prompt_parts)
            
            # Generate content - use higher default to avoid truncation
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens if max_tokens else 8192,  # Default to 8K tokens
            }
            
            # Add safety settings to avoid content blocking
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            
            logger.info(f"[Gemini] Sending request with max_output_tokens={generation_config['max_output_tokens']}")
            
            # Format tools for Gemini if provided.
            # Gemini expects "parameters" (Schema); MCP/OpenAI often use "inputSchema" -> normalize.
            gemini_tools = None
            if tools:
                function_declarations = []
                for t in tools:
                    decl = {
                        "name": t.get("name", ""),
                        "description": t.get("description", "") or "",
                    }
                    # Use "parameters" if present, else "inputSchema" (MCP/OpenAI style)
                    schema = t.get("parameters") or t.get("inputSchema")
                    if schema:
                        decl["parameters"] = schema
                    function_declarations.append(decl)
                gemini_tools = [{"function_declarations": function_declarations}]
                logger.info(f"[Gemini] Passing tools to Gemini: {[t.get('name') for t in tools]}")
            
            response = self.client.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings,
                tools=gemini_tools
            )
            
            # Log detailed response info
            if response.candidates:
                candidate = response.candidates[0]
                finish_reason = candidate.finish_reason
                logger.info(f"[Gemini] Finish reason: {finish_reason}")
                if hasattr(candidate, 'safety_ratings'):
                    logger.info(f"[Gemini] Safety ratings: {candidate.safety_ratings}")
                
                # Check for function call
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            fc = part.function_call
                            logger.info(f"[Gemini] Function call detected: {fc.name}")
                            
                            # Convert protobuf Map to dict safely
                            args_dict = {}
                            if hasattr(fc, 'args'):
                                try:
                                    # Convert to standard dict
                                    for key, value in fc.args.items():
                                        args_dict[key] = value
                                except:
                                    pass
                                    
                            return {
                                "function_call": {
                                    "name": fc.name,
                                    "arguments": args_dict
                                }
                            }
            
            # Check if response was blocked or empty
            # Return text if no function call
            text = ""
            try:
                text = response.text
            except ValueError:
                text = ""
                
            if not text:
                logger.warning(f"Gemini returned empty response. Finish reason: {response.candidates[0].finish_reason if response.candidates else 'unknown'}")
                return "I apologize, but I couldn't generate a response. Please try again."
            
            logger.info(f"[Gemini] Response length: {len(text)} chars")
            return text.strip()
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise
    
    def stream_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Generator[str, None, None]:
        """Generate streaming chat completion - yields text chunks as they arrive"""
        try:
            # Convert messages format for Gemini
            prompt_parts = []
            for msg in messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                if role == 'system':
                    prompt_parts.append(f"System: {content}")
                elif role == 'user':
                    prompt_parts.append(f"User: {content}")
                elif role == 'assistant':
                    prompt_parts.append(f"Assistant: {content}")
            
            prompt = "\n".join(prompt_parts)
            
            # Generate content with streaming
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens if max_tokens else 8192,
            }
            
            # Safety settings
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            
            logger.info(f"[Gemini] Starting streaming request")
            
            # Use stream=True for streaming response
            response = self.client.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings,
                stream=True
            )
            
            # Yield each chunk as it arrives
            for chunk in response:
                if chunk.text:
                    yield chunk.text
            
            logger.info(f"[Gemini] Streaming complete")
            
        except Exception as e:
            logger.error(f"Gemini streaming API error: {e}")
            raise

