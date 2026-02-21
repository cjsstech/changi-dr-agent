import os
import logging
from services.file_store_service import FileStorageService

logger = logging.getLogger(__name__)

# Base directory in S3 bucket
PROMPTS_DIR = "prompts/"

# Global storage instance
_storage = FileStorageService()

def load_prompt(prompt_file: str) -> str:
    """
    Load a prompt from S3
    
    Args:
        prompt_file: Name of the prompt file (e.g., 'travel_assistant.txt') or key
    
    Returns:
        Prompt content as string
    """
    try:
        # Construct key
        if prompt_file.startswith(PROMPTS_DIR):
            key = prompt_file
        else:
            key = f"{PROMPTS_DIR}{prompt_file}"
        
        if _storage.exists(key):
            data = _storage.read(key)
            content = data.decode('utf-8').strip()
            logger.info(f"Loaded prompt from S3: {key} ({len(content)} chars)")
            return content
        else:
            logger.error(f"Prompt file not found in S3: {key}")
            return ""
            
    except Exception as e:
        logger.error(f"Error loading prompt {prompt_file}: {e}")
        return ""

def save_prompt(filename: str, content: str) -> bool:
    """
    Save a prompt to S3
    """
    try:
        if filename.startswith(PROMPTS_DIR):
            key = filename
        else:
            key = f"{PROMPTS_DIR}{filename}"
            
        _storage.write(key, content.encode('utf-8'))
        logger.info(f"Saved prompt to S3: {key}")
        return True
    except Exception as e:
        logger.error(f"Error saving prompt {filename}: {e}")
        return False

def prompt_exists(filename: str) -> bool:
    """Check if prompt exists in S3"""
    try:
        if filename.startswith(PROMPTS_DIR):
            key = filename
        else:
            key = f"{PROMPTS_DIR}{filename}"
        return _storage.exists(key)
    except Exception:
        return False

def list_available_prompts() -> list:
    """
    List all available prompt files in S3 prompts directory
    
    Returns:
        List of prompt filenames (without directory prefix)
    """
    try:
        prompts = []
        files = _storage.list_files(PROMPTS_DIR)
        
        for key in files:
            # key is like "prompts/foo.txt"
            filename = os.path.basename(key) 
            if filename and filename.endswith('.txt'):
                prompts.append(filename)
                
        return sorted(prompts)
    except Exception as e:
        logger.error(f"Error listing prompts: {e}")
        return []

