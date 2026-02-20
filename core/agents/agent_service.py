"""
Agent Service - Handles CRUD operations for agent configurations (S3 storage)
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import os

from services.file_store_service import S3Storage  # adjust if needed

logger = logging.getLogger(__name__)


class AgentService:
    """Service for managing agent configurations using S3"""

    def __init__(self, storage_path: Optional[str] = None):
        # Keep same logical path as before
        self.storage_path = storage_path or os.environ.get('AGENTS_STORAGE_PATH', 'agents.json')
        self.storage = S3Storage()

    # ---------------------------------
    # Internal helpers
    # ---------------------------------

    def load_agents(self) -> Dict[str, Dict]:
        """Load all agents from S3"""
        try:
            if self.storage.exists(self.storage_path):
                data = self.storage.read(self.storage_path)
                agents = json.loads(data.decode("utf-8"))

                # Backward compatibility: convert list → dict
                if isinstance(agents, list):
                    agents_dict = {agent["id"]: agent for agent in agents}
                    self._save_agents_dict(agents_dict)
                    logger.info(
                        f"Agents loaded successfully (converted list to dict). "
                        f"Total agents: {len(agents_dict)}")  # Todo added for debugging remove once it is working

                    return agents_dict

                return agents

            return {}

        except Exception as e:
            logger.error(f"Error loading agents from S3: {e}")
            return {}

    def _save_agents_dict(self, agents: Dict[str, Dict]):
        """Save agents dictionary to S3"""
        try:
            data = json.dumps(
                agents,
                indent=2,
                ensure_ascii=False
            ).encode("utf-8")

            self.storage.write(self.storage_path, data)
            logger.info(
                f"Agents dictionary saved successfully to S3. "
                f"Total agents: {len(agents)}")  # Todo added for debugging remove once it is working

        except Exception as e:
            logger.error(f"Error saving agents to S3: {e}")
            raise

    # ---------------------------------
    # Public CRUD methods
    # ---------------------------------

    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """Get a specific agent by ID"""
        agents = self.load_agents()
        return agents.get(agent_id)

    def save_agent(self, agent_config: Dict) -> Dict:
        """Create or update an agent"""
        agents = self.load_agents()

        # Validate required fields
        required_fields = ["id", "name", "llm_provider", "llm_model"]
        for field in required_fields:
            if field not in agent_config:
                raise ValueError(f"Missing required field: {field}")

        # Must provide prompt_file or system_prompt
        if not agent_config.get("prompt_file") and not agent_config.get("system_prompt"):
            raise ValueError("Either 'prompt_file' or 'system_prompt' must be provided")

        now = datetime.utcnow().isoformat() + "Z"

        if agent_config["id"] in agents:
            # Update existing
            agent_config["updated_at"] = now
            agent_config["created_at"] = agents[agent_config["id"]].get("created_at", now)
            agent_config["created_by"] = agents[agent_config["id"]].get(
                "created_by",
                agent_config.get("created_by", "unknown")
            )
        else:
            # New agent
            agent_config["created_at"] = now
            agent_config["updated_at"] = now
            agent_config.setdefault("created_by", "unknown")

        agent_config.setdefault("mcp_tools", [])

        agents[agent_config["id"]] = agent_config
        self._save_agents_dict(agents)

        logger.info(f"Saved agent: {agent_config['id']}")
        return agent_config

    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent"""
        agents = self.load_agents()

        if agent_id in agents:
            del agents[agent_id]
            self._save_agents_dict(agents)
            logger.info(f"Deleted agent: {agent_id}")
            return True

        return False

    def list_agents(self) -> List[Dict]:
        """List all agents"""
        agents = self.load_agents()
        return list(agents.values())

    def agent_exists(self, agent_id: str) -> bool:
        """Check if an agent exists"""
        agents = self.load_agents()
        return agent_id in agents


# Global instance
agent_service = AgentService()

