"""
LangGraph Service - Handles workflow compilation and execution using LangGraph
"""
import logging
from typing import Dict, List, Any, Optional, Callable, Generator
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import LangGraph - graceful fallback if not installed
try:
    from langgraph.graph import StateGraph, START, END
    from langgraph.graph.state import CompiledStateGraph
    from typing_extensions import TypedDict
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logger.warning("LangGraph not installed. Workflow execution will not be available.")
    StateGraph = None
    CompiledStateGraph = None
    TypedDict = dict
    START = "__start__"
    END = "__end__"

from .agent_executor import AgentExecutor
from .workflow_service import workflow_service


class WorkflowState(TypedDict if LANGGRAPH_AVAILABLE else dict):
    """State that flows through the workflow"""
    messages: List[Dict[str, str]]  # Conversation history
    current_input: str              # Current user input
    current_output: str             # Output from last agent
    metadata: Dict[str, Any]        # Additional metadata (destinations, dates, etc.)
    agent_outputs: Dict[str, str]   # Outputs keyed by agent_id
    current_node: str               # Currently executing node
    workflow_id: str                # ID of the workflow being executed


class LangGraphService:
    """Service for compiling and executing LangGraph workflows"""
    
    def __init__(self):
        self._compiled_workflows: Dict[str, Any] = {}  # Cache compiled workflows
        self._agent_executors: Dict[str, AgentExecutor] = {}  # Cache agent executors
    
    def _get_agent_executor(self, agent_id: str) -> AgentExecutor:
        """Get or create an AgentExecutor for the given agent_id"""
        if agent_id not in self._agent_executors:
            self._agent_executors[agent_id] = AgentExecutor(agent_id)
        return self._agent_executors[agent_id]
    
    def _create_agent_node(self, agent_id: str, node_id: str) -> Callable:
        """
        Create a node function that wraps an AgentExecutor.
        
        Args:
            agent_id: ID of the agent to execute
            node_id: ID of the node in the workflow
            
        Returns:
            Callable that takes WorkflowState and returns updated WorkflowState
        """
        def agent_node(state: WorkflowState) -> WorkflowState:
            logger.info(f"[LangGraph] Executing agent node: {node_id} (agent: {agent_id})")
            
            try:
                executor = self._get_agent_executor(agent_id)
                
                # Use current input or last output as input to this agent
                user_message = state.get('current_input', '')
                if not user_message and state.get('current_output'):
                    user_message = state['current_output']
                
                # Build session context from state
                session_context = {
                    'conversation_history': state.get('messages', []),
                    'metadata': state.get('metadata', {})
                }
                
                # Execute the agent
                result = executor.chat(user_message, session_context)
                
                # Update state with agent output
                agent_output = result.get('response', '')
                
                return {
                    **state,
                    'current_output': agent_output,
                    'current_node': node_id,
                    'agent_outputs': {
                        **state.get('agent_outputs', {}),
                        agent_id: agent_output
                    },
                    'messages': [
                        *state.get('messages', []),
                        {'role': 'assistant', 'content': agent_output, 'agent_id': agent_id}
                    ],
                    'metadata': {
                        **state.get('metadata', {}),
                        **result.get('metadata', {}),
                        'destination': result.get('destination'),
                        'duration': result.get('duration'),
                        'locations': result.get('locations', []),
                        'full_itinerary': result.get('full_itinerary'),
                    }
                }
            except Exception as e:
                logger.error(f"[LangGraph] Error in agent node {node_id}: {e}")
                return {
                    **state,
                    'current_output': f"Error executing agent: {str(e)}",
                    'current_node': node_id
                }
        
        return agent_node
    
    def _create_conditional_router(self, conditions: List[Dict]) -> Callable:
        """
        Create a conditional router function.
        
        Args:
            conditions: List of condition configs with 'key' and 'target' 
            
        Returns:
            Callable that returns the next node based on state
        """
        def router(state: WorkflowState) -> str:
            metadata = state.get('metadata', {})
            output = state.get('current_output', '').lower()
            
            for condition in conditions:
                key = condition.get('key', '')
                target = condition.get('target', '')
                
                if key == 'default':
                    continue  # Handle default last
                
                # Check if condition key exists in metadata or output
                if key in metadata and metadata[key]:
                    logger.info(f"[LangGraph] Routing to {target} based on metadata key: {key}")
                    return target
                
                # Check if key phrase appears in output
                if key.lower() in output:
                    logger.info(f"[LangGraph] Routing to {target} based on output containing: {key}")
                    return target
            
            # Return default target
            for condition in conditions:
                if condition.get('key') == 'default':
                    logger.info(f"[LangGraph] Using default route to: {condition['target']}")
                    return condition['target']
            
            # If no default, return END
            logger.info("[LangGraph] No matching condition, routing to END")
            return END
        
        return router
    
    def compile_workflow(self, workflow_config: Dict) -> Optional[Any]:
        """
        Compile a workflow configuration into a LangGraph StateGraph.
        
        Args:
            workflow_config: Workflow configuration dict with nodes and edges
            
        Returns:
            Compiled StateGraph or None if compilation fails
        """
        if not LANGGRAPH_AVAILABLE:
            logger.error("LangGraph is not available. Cannot compile workflow.")
            return None
        
        workflow_id = workflow_config.get('id', 'unknown')
        logger.info(f"[LangGraph] Compiling workflow: {workflow_id}")
        
        try:
            # Create the state graph
            graph = StateGraph(WorkflowState)
            
            nodes = workflow_config.get('nodes', [])
            edges = workflow_config.get('edges', [])
            
            # Build node ID to node mapping
            node_map = {node['id']: node for node in nodes}
            
            # Add nodes to graph
            for node in nodes:
                node_id = node['id']
                node_type = node.get('type', 'agent')
                
                if node_type == 'start':
                    # Start node is handled specially via START constant
                    continue
                elif node_type == 'end':
                    # End node is handled specially via END constant
                    continue
                elif node_type in ('agent', 'orchestrator'):
                    # Both agent and orchestrator nodes run agents
                    # Orchestrator is just a visual distinction in the UI
                    agent_id = node.get('agent_id')
                    if not agent_id:
                        logger.warning(f"Agent node {node_id} missing agent_id, skipping")
                        continue
                    graph.add_node(node_id, self._create_agent_node(agent_id, node_id))
                elif node_type == 'conditional':
                    # Conditional nodes are handled as routing edges, not as nodes
                    # We'll add a passthrough node
                    graph.add_node(node_id, lambda state: state)
                else:
                    logger.warning(f"Unknown node type: {node_type} for node {node_id}")

            
            # Add edges
            has_start_edge = False
            for edge in edges:
                source = edge.get('source')
                target = edge.get('target')
                condition = edge.get('condition')
                
                source_node = node_map.get(source, {})
                target_node = node_map.get(target, {})
                
                # Handle start node
                if source_node.get('type') == 'start':
                    source = START
                    has_start_edge = True
                
                # Handle end node
                if target_node.get('type') == 'end':
                    target = END
                
                # Handle conditional edges
                if source_node.get('type') == 'conditional':
                    # For conditional nodes, we need to add conditional edges
                    conditions = source_node.get('conditions', [])
                    if conditions:
                        # Create a mapping of condition results to targets
                        condition_map = {}
                        for cond in conditions:
                            cond_target = cond.get('target')
                            if node_map.get(cond_target, {}).get('type') == 'end':
                                condition_map[cond['key']] = END
                            else:
                                condition_map[cond['key']] = cond_target
                        
                        graph.add_conditional_edges(
                            source,
                            self._create_conditional_router(conditions),
                            condition_map
                        )
                else:
                    # Regular edge
                    graph.add_edge(source, target)
            
            # If no START edge was explicitly defined via a 'start' node type, 
            # try to auto-detect the start node (a node with no incoming edges)
            if not has_start_edge and nodes:
                targets = {edge.get('target') for edge in edges}
                start_node_id = None
                
                for node in nodes:
                    if node['id'] not in targets and node.get('type') != 'end':
                        start_node_id = node['id']
                        break
                        
                # Fallback to the first node if we can't find one without incoming edges
                if not start_node_id and nodes:
                    start_node_id = nodes[0]['id']
                    
                if start_node_id:
                    graph.add_edge(START, start_node_id)
                    logger.info(f"[LangGraph] Auto-added edge from START to entrypoint node: {start_node_id}")
            
            # Compile the graph
            compiled = graph.compile()
            
            # Cache the compiled workflow
            self._compiled_workflows[workflow_id] = compiled
            
            logger.info(f"[LangGraph] Successfully compiled workflow: {workflow_id}")
            return compiled
            
        except Exception as e:
            logger.error(f"[LangGraph] Error compiling workflow {workflow_id}: {e}")
            return None
    
    def execute_workflow(
        self,
        workflow_id: str,
        user_message: str,
        session_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Execute a workflow with the given user message.
        
        Args:
            workflow_id: ID of the workflow to execute
            user_message: User's input message
            session_context: Optional session context
            
        Returns:
            Dict with response, success status, and metadata
        """
        if not LANGGRAPH_AVAILABLE:
            return {
                'success': False,
                'error': 'LangGraph is not available',
                'response': 'Workflow execution requires LangGraph to be installed.'
            }
        
        # Get workflow config
        workflow_config = workflow_service.get_workflow(workflow_id)
        if not workflow_config:
            return {
                'success': False,
                'error': f'Workflow not found: {workflow_id}',
                'response': f'The requested workflow "{workflow_id}" was not found.'
            }
        
        # Compile workflow (uses cache if available)
        compiled = self._compiled_workflows.get(workflow_id)
        if not compiled:
            compiled = self.compile_workflow(workflow_config)
        
        if not compiled:
            return {
                'success': False,
                'error': 'Failed to compile workflow',
                'response': 'There was an error compiling the workflow.'
            }
        
        try:
            # Initialize state
            initial_state: WorkflowState = {
                'messages': session_context.get('conversation_history', []) if session_context else [],
                'current_input': user_message,
                'current_output': '',
                'metadata': session_context.get('metadata', {}) if session_context else {},
                'agent_outputs': {},
                'current_node': '',
                'workflow_id': workflow_id
            }
            
            # Execute the workflow
            logger.info(f"[LangGraph] Executing workflow: {workflow_id}")
            final_state = compiled.invoke(initial_state)
            
            logger.info(f"[LangGraph] Workflow execution complete: {workflow_id}")
            
            return {
                'success': True,
                'response': final_state.get('current_output', ''),
                'workflow_id': workflow_id,
                'agent_outputs': final_state.get('agent_outputs', {}),
                'metadata': final_state.get('metadata', {}),
                'messages': final_state.get('messages', []),
                'full_itinerary': final_state.get('metadata', {}).get('full_itinerary'),
                'destination': final_state.get('metadata', {}).get('destination'),
                'duration': final_state.get('metadata', {}).get('duration'),
                'locations': final_state.get('metadata', {}).get('locations', [])
            }
            
        except Exception as e:
            logger.error(f"[LangGraph] Error executing workflow {workflow_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'response': f'Error executing workflow: {str(e)}'
            }
    
    def execute_workflow_stream(
        self,
        workflow_id: str,
        user_message: str,
        session_context: Optional[Dict] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Execute a workflow with streaming output.
        
        Yields events as workflow progresses through nodes.
        """
        if not LANGGRAPH_AVAILABLE:
            yield {
                'type': 'error',
                'error': 'LangGraph is not available'
            }
            return
        
        workflow_config = workflow_service.get_workflow(workflow_id)
        if not workflow_config:
            yield {
                'type': 'error',
                'error': f'Workflow not found: {workflow_id}'
            }
            return
        
        compiled = self._compiled_workflows.get(workflow_id)
        if not compiled:
            compiled = self.compile_workflow(workflow_config)
        
        if not compiled:
            yield {
                'type': 'error',
                'error': 'Failed to compile workflow'
            }
            return
        
        try:
            initial_state: WorkflowState = {
                'messages': session_context.get('conversation_history', []) if session_context else [],
                'current_input': user_message,
                'current_output': '',
                'metadata': session_context.get('metadata', {}) if session_context else {},
                'agent_outputs': {},
                'current_node': '',
                'workflow_id': workflow_id
            }
            
            # Stream execution
            for event in compiled.stream(initial_state):
                # Each event is a dict with node name and output
                for node_name, node_output in event.items():
                    yield {
                        'type': 'node_complete',
                        'node': node_name,
                        'output': node_output.get('current_output', ''),
                        'metadata': node_output.get('metadata', {})
                    }
            
            # Final state
            yield {
                'type': 'done',
                'success': True,
                'workflow_id': workflow_id
            }
            
        except Exception as e:
            logger.error(f"[LangGraph] Stream error for workflow {workflow_id}: {e}")
            yield {
                'type': 'error',
                'error': str(e)
            }
    
    def invalidate_cache(self, workflow_id: str):
        """Invalidate cached compiled workflow"""
        if workflow_id in self._compiled_workflows:
            del self._compiled_workflows[workflow_id]
            logger.info(f"[LangGraph] Invalidated cache for workflow: {workflow_id}")
    
    def get_workflow_visualization(self, workflow_id: str) -> Optional[Dict]:
        """
        Get workflow visualization data for the frontend.
        
        Returns node and edge data formatted for React Flow or similar.
        """
        workflow_config = workflow_service.get_workflow(workflow_id)
        if not workflow_config:
            return None
        
        # Transform nodes for visualization
        viz_nodes = []
        for node in workflow_config.get('nodes', []):
            viz_node = {
                'id': node['id'],
                'type': node.get('type', 'agent'),
                'position': node.get('position', {'x': 0, 'y': 0}),
                'data': {
                    'label': node.get('label', node['id']),
                    'agent_id': node.get('agent_id'),
                    'conditions': node.get('conditions', [])
                }
            }
            viz_nodes.append(viz_node)
        
        # Transform edges for visualization
        viz_edges = []
        for edge in workflow_config.get('edges', []):
            viz_edge = {
                'id': f"{edge['source']}-{edge['target']}",
                'source': edge['source'],
                'target': edge['target'],
                'type': 'conditional' if edge.get('condition') else 'default',
                'label': edge.get('condition', '')
            }
            viz_edges.append(viz_edge)
        
        return {
            'nodes': viz_nodes,
            'edges': viz_edges,
            'workflow': {
                'id': workflow_config['id'],
                'name': workflow_config.get('name', ''),
                'description': workflow_config.get('description', '')
            }
        }


# Global instance
langgraph_service = LangGraphService()

