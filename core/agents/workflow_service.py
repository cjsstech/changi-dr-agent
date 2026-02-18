"""
Workflow Service - Handles CRUD operations for workflow configurations
"""
import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional
import config

from services.file_store_service import S3Storage

logger = logging.getLogger(__name__)


class WorkflowService:
    """Service for managing workflow configurations"""
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or getattr(config, 'WORKFLOWS_STORAGE_PATH', 'storage/workflows.json')
        self.storage = S3Storage()
    
    def load_workflows(self) -> Dict[str, Dict]:
        """Load all workflows from storage"""
        try:
            if self.storage.exists(self.storage_path):
                data = self.storage.read(self.storage_path)
                return json.loads(data.decode('utf-8'))
            return {}
        except Exception as e:
            logger.error(f"Error loading workflows: {e}")
            return {}
    
    def _save_workflows_dict(self, workflows: Dict[str, Dict]):
        """Save workflows dictionary to storage"""
        try:
            data = json.dumps(workflows, indent=2, ensure_ascii=False).encode('utf-8')
            self.storage.write(self.storage_path, data)
        except Exception as e:
            logger.error(f"Error saving workflows: {e}")
            raise
    
    def get_workflow(self, workflow_id: str) -> Optional[Dict]:
        """Get a specific workflow by ID"""
        workflows = self.load_workflows()
        return workflows.get(workflow_id)
    
    def save_workflow(self, workflow_config: Dict) -> Dict:
        """Save or update a workflow configuration"""
        workflows = self.load_workflows()
        
        # Validate required fields
        required_fields = ['id', 'name']
        for field in required_fields:
            if field not in workflow_config:
                raise ValueError(f"Missing required field: {field}")
        
        # Ensure nodes and edges exist
        if 'nodes' not in workflow_config:
            workflow_config['nodes'] = []
        if 'edges' not in workflow_config:
            workflow_config['edges'] = []
        
        # Set timestamps
        now = datetime.utcnow().isoformat() + 'Z'
        if workflow_config['id'] in workflows:
            # Update existing workflow
            workflow_config['updated_at'] = now
            workflow_config['created_at'] = workflows[workflow_config['id']].get('created_at', now)
            workflow_config['created_by'] = workflows[workflow_config['id']].get('created_by', workflow_config.get('created_by', 'unknown'))
        else:
            # New workflow
            workflow_config['created_at'] = now
            workflow_config['updated_at'] = now
            if 'created_by' not in workflow_config:
                workflow_config['created_by'] = 'unknown'
        
        # Save workflow
        workflows[workflow_config['id']] = workflow_config
        self._save_workflows_dict(workflows)
        
        logger.info(f"Saved workflow: {workflow_config['id']}")
        return workflow_config
    
    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow by ID"""
        workflows = self.load_workflows()
        if workflow_id in workflows:
            del workflows[workflow_id]
            self._save_workflows_dict(workflows)
            logger.info(f"Deleted workflow: {workflow_id}")
            return True
        return False
    
    def list_workflows(self) -> List[Dict]:
        """List all workflows"""
        workflows = self.load_workflows()
        return list(workflows.values())
    
    def workflow_exists(self, workflow_id: str) -> bool:
        """Check if a workflow exists"""
        workflows = self.load_workflows()
        return workflow_id in workflows
    
    def validate_workflow(self, workflow_config: Dict) -> tuple[bool, List[str]]:
        """
        Validate a workflow configuration.
        
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        # Check required fields
        if 'id' not in workflow_config:
            errors.append("Workflow ID is required")
        if 'name' not in workflow_config:
            errors.append("Workflow name is required")
        
        nodes = workflow_config.get('nodes', [])
        edges = workflow_config.get('edges', [])
        
        # Check for at least one node
        if len(nodes) == 0:
            errors.append("Workflow must have at least one node")
        
        # Validate node IDs are unique
        node_ids = [node.get('id') for node in nodes]
        if len(node_ids) != len(set(node_ids)):
            errors.append("Node IDs must be unique")
        
        # Validate edges reference valid nodes
        for edge in edges:
            source = edge.get('source')
            target = edge.get('target')
            if source not in node_ids:
                errors.append(f"Edge source '{source}' references non-existent node")
            if target not in node_ids:
                errors.append(f"Edge target '{target}' references non-existent node")
        
        # Check that agent/orchestrator nodes have agents assigned
        for node in nodes:
            node_type = node.get('type', 'agent')
            if node_type in ('agent', 'orchestrator'):
                if not node.get('agent_id'):
                    errors.append(f"Node '{node.get('id')}' requires an agent to be selected")
        
        return (len(errors) == 0, errors)



# Global instance
workflow_service = WorkflowService()

