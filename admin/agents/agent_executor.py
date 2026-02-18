"""
Agent Executor - Handles agent execution
This is a simplified version - customize for your LLM providers
"""
import logging
import os
from typing import Dict, Any, Optional, Generator

logger = logging.getLogger(__name__)

# Import agent service
from .agent_service import agent_service

# Try to import OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI not available")

# Try to import Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("Gemini not available")


class AgentExecutor:
    """
    Executes an agent with a specific configuration.
    Customize this class for your LLM providers and tools.
    """
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.agent_config = agent_service.get_agent(agent_id)
        
        if not self.agent_config:
            raise ValueError(f"Agent not found: {agent_id}")
        
        self.llm_provider = self.agent_config.get('llm_provider', 'openai')
        self.llm_model = self.agent_config.get('llm_model', 'gpt-4o')
        self.system_prompt = self._load_system_prompt()
        
        # Initialize LLM client
        self._init_llm_client()
    
    def _load_system_prompt(self) -> str:
        """Load the system prompt from file or config"""
        # Check for prompt file
        prompt_file = self.agent_config.get('prompt_file')
        if prompt_file:
            prompts_dir = os.environ.get('PROMPTS_DIR', 'prompts')
            filepath = os.path.join(prompts_dir, prompt_file)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return f.read()
        
        # Fall back to inline system prompt
        return self.agent_config.get('system_prompt', 'You are a helpful AI assistant.')
    
    def _init_llm_client(self):
        """Initialize the LLM client based on provider"""
        if self.llm_provider == 'openai' and OPENAI_AVAILABLE:
            api_key = os.environ.get('OPENAI_API_KEY')
            if api_key:
                self.client = OpenAI(api_key=api_key)
            else:
                logger.warning("OpenAI API key not set")
                self.client = None
        elif self.llm_provider == 'gemini' and GEMINI_AVAILABLE:
            api_key = os.environ.get('GOOGLE_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                self.client = genai.GenerativeModel(self.llm_model)
            else:
                logger.warning("Google API key not set")
                self.client = None
        else:
            self.client = None
            logger.warning(f"No client available for provider: {self.llm_provider}")
    
    def chat(self, user_message: str, session_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Process a user message and return a response.
        
        Args:
            user_message: The user's input message
            session_context: Optional context with conversation history
            
        Returns:
            Dict with 'response' and optional metadata
        """
        if not self.client:
            return {
                'response': 'LLM client not configured. Please set API keys.',
                'success': False
            }
        
        try:
            # Build messages
            messages = [{'role': 'system', 'content': self.system_prompt}]
            
            # Add conversation history if provided
            if session_context and 'conversation_history' in session_context:
                for msg in session_context['conversation_history']:
                    messages.append({
                        'role': msg.get('role', 'user'),
                        'content': msg.get('content', '')
                    })
            
            # Add current user message
            messages.append({'role': 'user', 'content': user_message})
            
            # Call LLM
            if self.llm_provider == 'openai':
                response = self.client.chat.completions.create(
                    model=self.llm_model,
                    messages=messages
                )
                assistant_message = response.choices[0].message.content
            
            elif self.llm_provider == 'gemini':
                # Convert to Gemini format
                gemini_messages = []
                for msg in messages[1:]:  # Skip system message for Gemini
                    role = 'user' if msg['role'] == 'user' else 'model'
                    gemini_messages.append({'role': role, 'parts': [msg['content']]})
                
                chat = self.client.start_chat(history=gemini_messages[:-1])
                response = chat.send_message(user_message)
                assistant_message = response.text
            
            else:
                return {'response': 'Unsupported LLM provider', 'success': False}
            
            return {
                'response': assistant_message,
                'success': True,
                'agent_id': self.agent_id,
                'model': self.llm_model
            }
            
        except Exception as e:
            logger.error(f"Error in agent execution: {e}")
            return {
                'response': f'Error: {str(e)}',
                'success': False
            }
    
    def chat_stream(self, user_message: str, session_context: Optional[Dict] = None) -> Generator[str, None, None]:
        """
        Stream a response from the agent.
        
        Yields chunks of the response as they are generated.
        """
        if not self.client:
            yield "LLM client not configured."
            return
        
        try:
            messages = [{'role': 'system', 'content': self.system_prompt}]
            
            if session_context and 'conversation_history' in session_context:
                for msg in session_context['conversation_history']:
                    messages.append({
                        'role': msg.get('role', 'user'),
                        'content': msg.get('content', '')
                    })
            
            messages.append({'role': 'user', 'content': user_message})
            
            if self.llm_provider == 'openai':
                response = self.client.chat.completions.create(
                    model=self.llm_model,
                    messages=messages,
                    stream=True
                )
                
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            
            elif self.llm_provider == 'gemini':
                gemini_messages = []
                for msg in messages[1:]:
                    role = 'user' if msg['role'] == 'user' else 'model'
                    gemini_messages.append({'role': role, 'parts': [msg['content']]})
                
                chat = self.client.start_chat(history=gemini_messages[:-1])
                response = chat.send_message(user_message, stream=True)
                
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
                        
        except Exception as e:
            logger.error(f"Error in streaming: {e}")
            yield f"Error: {str(e)}"
