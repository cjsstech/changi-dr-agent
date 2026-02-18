#/chat/app.py
"""
Chat Application Controller to Load Web pages as well as process user requests
"""
from core.web.app_tools import render_template, jsonify, session, redirect, url_for, Response
from core.web.lambda_request import LambdaRequest
import os
import json
from typing import List, Dict
from dotenv import load_dotenv
import config
import logging
from core.agents.agent_service import agent_service
from core.agents.agent_executor import AgentExecutor
from core.agents.workflow_service import workflow_service
from core.agents.langgraph_service import langgraph_service
from core.auth.auth_service import auth_service
from core.agents.mcp_manager import mcp_manager
from core.prompts.prompt_loader import list_available_prompts, load_prompt, save_prompt, prompt_exists, PROMPTS_DIR

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

#TODO Flask Code not needed for Lambda
# app = Flask(__name__)
# app.secret_key = os.urandom(24)  # For session management
# app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)


# Initialize default agent if it doesn't exist
def initialize_default_agent():
    """Initialize default agents from core/storage/agents.json"""
    try:
        default_agent_id = config.DEFAULT_AGENT_ID
        logging.info(f"Checking if default agent '{default_agent_id}' exists...")

        # Load all agents from the storage file
        project_root = os.path.dirname(os.path.dirname(__file__))  # up from chat/ to project root
        storage_agents_path = os.path.join(project_root, 'core', 'storage', 'agents.json')
        default_agents_path = os.path.join(project_root, 'core', 'agents', 'default_agents.json')

        # Prefer core/storage/agents.json (has all agents), fallback to default_agents.json
        agents_path = storage_agents_path if os.path.exists(storage_agents_path) else default_agents_path
        logging.info(f"Loading agents from: {agents_path}")

        if os.path.exists(agents_path):
            with open(agents_path, 'r', encoding='utf-8') as f:
                all_agents = json.load(f)

            seeded_count = 0
            for agent_id, agent_data in all_agents.items():
                if not agent_service.agent_exists(agent_id):
                    agent_service.save_agent(agent_data)
                    logging.info(f"Seeded agent: {agent_id} ({agent_data.get('name', 'unknown')})")
                    seeded_count += 1
                else:
                    logging.info(f"Agent '{agent_id}' already exists, skipping")

            if seeded_count > 0:
                logging.info(f"Seeded {seeded_count} new agent(s)")
            else:
                logging.info("All agents already exist in storage")
        else:
            logging.error(f"No agents file found at: {agents_path}")

        # Also seed workflows from core/storage/workflows.json
        workflows_path = os.path.join(project_root, 'core', 'storage', 'workflows.json')
        if os.path.exists(workflows_path):
            with open(workflows_path, 'r', encoding='utf-8') as f:
                all_workflows = json.load(f)
            wf_seeded = 0
            for wf_id, wf_data in all_workflows.items():
                if not workflow_service.workflow_exists(wf_id):
                    workflow_service.save_workflow(wf_data)
                    logging.info(f"Seeded workflow: {wf_id} ({wf_data.get('name', 'unknown')})")
                    wf_seeded += 1
                else:
                    logging.info(f"Workflow '{wf_id}' already exists, skipping")
            if wf_seeded > 0:
                logging.info(f"Seeded {wf_seeded} new workflow(s)")
        else:
            logging.info("No workflows file found, skipping workflow seeding")

        # Also seed prompt files from core/prompts/*.txt to S3
        local_prompts_dir = os.path.join(project_root, 'core', 'prompts')
        if os.path.isdir(local_prompts_dir):
            for fname in os.listdir(local_prompts_dir):
                if fname.endswith('.txt') and not fname.startswith('.'):
                    if not prompt_exists(fname):
                        fpath = os.path.join(local_prompts_dir, fname)
                        with open(fpath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        save_prompt(fname, content)
                        logging.info(f"Seeded prompt to S3: {fname}")
                    else:
                        logging.info(f"Prompt '{fname}' already exists in S3, skipping")

    except Exception as e:
        logging.error(f"Error initializing default agent: {e}", exc_info=True)


# Initialize default agent on startup
try:
    initialize_default_agent()
except Exception as e:
    logging.warning(f"Could not initialize default agent on startup: {e}")


# ============================================================================
# Authentication Routes
# ============================================================================

#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/login', methods=['GET', 'POST'])
def login(request: LambdaRequest) -> Response:#Shadows name 'request' from outer scope  ??
    """Login page and handler"""
    if request.method == 'POST':
        username = request.body.get('username')
        password = request.body.get('password')

        if auth_service.login(username, password):
            next_url = request.args.get('next') or url_for('admin')
            return redirect(next_url)
        else:
            return render_template('login.html', error='Invalid username or password')

    return render_template('login.html')


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/logout')
def logout(request: LambdaRequest):
    """Logout handler"""
    auth_service.logout()
    return redirect(url_for('index'))


# ============================================================================
# Main Routes
# ============================================================================

#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/')
def index(request: LambdaRequest):
    """Redirect to default agent"""
    default_agent_id = config.DEFAULT_AGENT_ID
    return redirect(url_for('agent_chat', agent_id=default_agent_id))


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/agent/<agent_id>') TODO needs handle this in lambda handler
def agent_chat(request: LambdaRequest):
    """Agent chat interface"""
    agent_id = request.args.get('agent_id')
    agent = agent_service.get_agent(agent_id)
    if not agent:
        # Try to initialize default agent if it doesn't exist yet (Lambda cold start)
        initialize_default_agent()
        agent = agent_service.get_agent(agent_id)
    if not agent:
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": f"Agent {agent_id} not found"
        }

    # Determine agent type for quick prompts
    agent_name_lower = agent.get('name', '').lower()
    agent_desc_lower = agent.get('description', '').lower()

    # Get agent-specific quick prompts
    quick_prompts = get_agent_quick_prompts(agent_name_lower, agent_desc_lower)

    return render_template('index.html', agent=agent, quick_prompts=quick_prompts)


def get_agent_quick_prompts(agent_name: str, agent_desc: str) -> List[Dict]:
    """Get agent-specific quick prompts"""
    # Check if it's a roaming agent
    if any(keyword in agent_name or keyword in agent_desc for keyword in ['roaming', 'sim', 'data plan']):
        return [
            {'text': '🌏 Asia', 'prompt': 'I need a roaming plan for Asia'},
            {'text': '🇪🇺 Europe', 'prompt': 'I need a roaming plan for Europe'},
            {'text': '🇺🇸 Americas', 'prompt': 'I need a roaming plan for Americas'},
            {'text': '📱 Heavy Data', 'prompt': 'I need a roaming plan with heavy data usage'},
            {'text': '💰 Budget', 'prompt': 'Show me budget-friendly roaming plans'}
        ]

    # Check if it's a travel agent
    elif any(keyword in agent_name or keyword in agent_desc for keyword in ['travel', 'itinerary', 'trip planner']):
        return [
            {'text': '🗾 Tokyo', 'prompt': 'Plan a 5-day trip to Tokyo'},
            {'text': '🏝️ Weekend', 'prompt': 'Weekend getaway from Singapore'},
            {'text': '👨‍👩‍👧 Family', 'prompt': 'Family vacation ideas'},
            {'text': '💑 Romantic', 'prompt': 'Romantic destination for couples'},
            {'text': '🏔️ Adventure', 'prompt': 'Adventure travel in Southeast Asia'}
        ]

    # Default prompts for other agents
    else:
        return [
            {'text': '💬 Help', 'prompt': 'How can you help me?'},
            {'text': '❓ Questions', 'prompt': 'I have some questions'},
            {'text': 'ℹ️ Info', 'prompt': 'Tell me more about your services'}
        ]


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/api/reset', methods=['POST'])
def reset_session(request: LambdaRequest):  # TODO needs handle this in dynamo session handling
    """Reset/clear the chat session"""
    try:
        # Clear all agent-related session data

        keys_to_remove = [key for key in session.keys() if key.startswith('agent_') or key == 'context']
        for key in keys_to_remove:
            session.pop(key, None)
        logging.info("Session reset successfully")
        return jsonify({'success': True, 'message': 'Session cleared'})
    except Exception as e:
        logging.error(f"Error resetting session: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/agent/<agent_id>/chat', methods=['POST'])
def agent_chat_api(request:LambdaRequest):
    """Agent chat API endpoint"""
    try:
        agent_id = request.args.get('agent_id')
        agent = agent_service.get_agent(agent_id)
        if not agent:
            return jsonify({'error': f'Agent {agent_id} not found', 'success': False}), 404

        data = request.body
        user_message = data.get('message', '')
        selected_flight_index = data.get('selected_flight_index')  # For flight selection

        if not user_message and selected_flight_index is None:
            return jsonify({'error': 'No message provided', 'success': False}), 400

        # TODO needs handle this in dynamo session handling
        # Initialize session context if not exists
        session_key = f'agent_{agent_id}_context'
        if session_key not in session:
            session[session_key] = {}

        session_context = session[session_key]

        # Handle flight selection
        if selected_flight_index is not None and 'available_flights' in session_context:
            flights = session_context.get('available_flights', [])
            if 0 <= selected_flight_index < len(flights):
                selected_flight = flights[selected_flight_index]
                # Extract arrival time from selected flight
                arrival_time = _extract_arrival_time(selected_flight)
                session_context['selected_flight'] = selected_flight
                session_context['arrival_time'] = arrival_time
                # Continue with itinerary generation
                user_message = f"I've selected flight {selected_flight.get('flight_number', '')}. Please generate my itinerary."

        # Execute agent
        executor = AgentExecutor(agent_id)
        result = executor.chat(user_message, session_context)

        # Save session context
        session[session_key] = session_context

        return jsonify(result)

    except Exception as e:
        logging.error(f"Error in agent chat API: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/agent/<agent_id>/chat/stream', methods=['POST'])
def agent_chat_stream_api(request:LambdaRequest):
    """Agent chat API endpoint with Server-Sent Events (SSE) streaming"""
    try:
        agent_id = request.args.get('agent_id')
        agent = agent_service.get_agent(agent_id)
        if not agent:
            return jsonify({'error': f'Agent {agent_id} not found', 'success': False}), 404

        data = request.body
        user_message = data.get('message', '')

        if not user_message:
            return jsonify({'error': 'No message provided', 'success': False}), 400

        # Initialize session context if not exists
        session_key = f'agent_{agent_id}_context'
        if session_key not in session:
            session[session_key] = {}

        session_context = session[session_key]

        def generate():
            """Generator function for SSE streaming"""
            executor = AgentExecutor(agent_id)

            for event in executor.chat_stream(user_message, session_context):
                event_type = event.get('type', 'chunk')

                if event_type == 'chunk':
                    # Stream text chunk
                    chunk_data = json.dumps({'type': 'chunk', 'content': event.get('content', '')})
                    yield f"data: {chunk_data}\n\n"

                elif event_type == 'done':
                    # Final event with complete response
                    done_data = json.dumps({
                        'type': 'done',
                        'response': event.get('response', ''),
                        'success': event.get('success', True),
                        'agent_id': event.get('agent_id'),
                        'agent_name': event.get('agent_name')
                    })
                    yield f"data: {done_data}\n\n"

                elif event_type == 'error':
                    # Error event
                    error_data = json.dumps({
                        'type': 'error',
                        'error': event.get('error', 'Unknown error'),
                        'success': False
                    })
                    yield f"data: {error_data}\n\n"

            # Note: Cannot save session inside generator (outside request context)
            # Session modifications to session_context persist via reference

        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'  # Disable nginx buffering
            }
        )

    except Exception as e:
        logging.error(f"Error in agent chat stream API: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


def _extract_arrival_time(flight_data):
    """Extract arrival time from flight data"""
    from datetime import datetime, timedelta

    try:
        display_timestamp = flight_data.get("display_timestamp")
        if display_timestamp:
            dt_obj = datetime.strptime(display_timestamp, "%Y-%m-%d %H:%M")
            # Estimate arrival time (add 2-4 hours for typical Southeast Asian flights)
            # This is a rough estimate - in production, you'd get actual flight duration
            estimated_duration = timedelta(hours=2.5)  # Average for SEA flights
            arrival_dt = dt_obj + estimated_duration
            return arrival_dt.strftime("%H:%M")
    except:
        pass

    return None


# ============================================================================
# Admin Routes (Protected)
# ============================================================================

#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/admin')
@auth_service.require_auth
def admin(request=None):
    """Agent management UI"""
    agents = agent_service.list_agents()
    available_tools = [{'id': tid, **tinfo} for tid, tinfo in mcp_manager.tools.items() if tinfo.get('enabled', False)]
    available_prompts = list_available_prompts()
    return render_template('admin.html', agents=agents, available_tools=available_tools,
                           available_prompts=available_prompts)


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/admin/agents', methods=['GET', 'POST'])
@auth_service.require_auth
def admin_agents(request:LambdaRequest):
    """Create or list agents"""
    if request.method == 'GET':
        agents = agent_service.list_agents()
        return jsonify({'success': True, 'agents': agents})

    # POST - Create agent
    try:
        data = request.body

        if not data:
            return jsonify({'error': 'No JSON data provided', 'success': False}), 400

        # Validate required fields - either prompt_file or system_prompt must be provided
        required_fields = ['id', 'name', 'llm_provider', 'llm_model']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}', 'success': False}), 400

        # Either prompt_file or system_prompt must be provided
        if not data.get('prompt_file') and not data.get('system_prompt'):
            return jsonify({'error': 'Either prompt_file or system_prompt must be provided', 'success': False}), 400

        # Set created_by from session
        user = auth_service.get_current_user()
        data['created_by'] = user['username'] if user else 'unknown'

        # Save agent
        agent = agent_service.save_agent(data)
        return jsonify({'agent': agent, 'success': True}), 201

    except Exception as e:
        logging.error(f"Error creating agent: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/admin/agents/<agent_id>', methods=['GET', 'PUT', 'DELETE'])
@auth_service.require_auth
def admin_agent(request:LambdaRequest):
    """Get, update, or delete a specific agent"""
    agent_id = request.args.get('agent_id')
    if request.method == 'GET':
        agent = agent_service.get_agent(agent_id)
        if not agent:
            return jsonify({'error': 'Agent not found', 'success': False}), 404
        return jsonify({'agent': agent, 'success': True})

    elif request.method == 'PUT':
        # Update agent
        try:
            data = request.body

            if not data:
                return jsonify({'error': 'No JSON data provided', 'success': False}), 400

            data['id'] = agent_id  # Ensure ID matches

            # Set updated_by from session
            user = auth_service.get_current_user()
            if user:
                data['created_by'] = agent_service.get_agent(agent_id).get('created_by', user['username'])

            agent = agent_service.save_agent(data)
            return jsonify({'agent': agent, 'success': True})

        except Exception as e:
            logging.error(f"Error updating agent: {e}")
            return jsonify({'error': str(e), 'success': False}), 500

    elif request.method == 'DELETE':
        # Delete agent
        if agent_service.delete_agent(agent_id):
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Agent not found', 'success': False}), 404


# ============================================================================
# Prompts Routes (Protected)
# ============================================================================

#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/admin/prompts', methods=['GET'])
@auth_service.require_auth
def admin_prompts(request=None):
    """List all prompts with content preview"""
    try:
        prompts = []
        prompt_files = list_available_prompts()
        for filename in prompt_files:
            content = load_prompt(filename)
            prompts.append({
                'filename': filename,
                'content': content,
                'preview': content[:200] + '...' if len(content) > 200 else content,
                'lines': len(content.split('\n')),
                'chars': len(content)
            })
        return jsonify({'success': True, 'prompts': prompts})
    except Exception as e:
        logging.error(f"Error listing prompts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/admin/prompts/<filename>', methods=['GET', 'PUT'])
@auth_service.require_auth
def admin_prompt(request:LambdaRequest):
    """Get or update a specific prompt"""
    import os
    filename = request.args.get('file_name')
    if request.method == 'GET':
        content = load_prompt(filename)
        if not content:
            return jsonify({'success': False, 'error': 'Prompt not found'}), 404
        return jsonify({
            'success': True,
            'prompt': {
                'filename': filename,
                'content': content
            }
        })

    elif request.method == 'PUT':
        try:
            data = request.body # LambdaRequest body is parsed JSON or dict
            if not data or 'content' not in data:
                return jsonify({'success': False, 'error': 'Content is required'}), 400

            # Ensure filename ends with .txt
            if not filename.endswith('.txt'):
                filename = filename + '.txt'

            # Save to S3 via prompt_loader
            if save_prompt(filename, data['content']):
                logging.info(f"Saved prompt: {filename}")
                return jsonify({'success': True, 'filename': filename})
            else:
                 return jsonify({'success': False, 'error': 'Failed to save prompt'}), 500

        except Exception as e:
            logging.error(f"Error saving prompt: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/admin/prompts', methods=['POST'])
@auth_service.require_auth
def create_prompt(request:LambdaRequest):
    """Create a new prompt file"""
    import os

    try:
        data = request.body
        if not data or 'filename' not in data or 'content' not in data:
            return jsonify({'success': False, 'error': 'Filename and content are required'}), 400

        filename = data['filename']

        # Ensure filename ends with .txt
        if not filename.endswith('.txt'):
            filename = filename + '.txt'

        # Check if file already exists
        if prompt_exists(filename):
            return jsonify({'success': False, 'error': 'Prompt file already exists'}), 400

        if save_prompt(filename, data['content']):
            logging.info(f"Created new prompt: {filename}")
            return jsonify({'success': True, 'filename': filename}), 201
        else:
             return jsonify({'success': False, 'error': 'Failed to save prompt'}), 500

    except Exception as e:
        logging.error(f"Error creating prompt: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/admin/mcp/tools', methods=['GET'])
@auth_service.require_auth
def admin_mcp_tools(request=None):
    """Get all MCP tools (enabled and disabled)"""


    tools = []
    for tool_id, tool_info in mcp_manager.tools.items():
        tools.append({
            'id': tool_id,
            **tool_info
        })
    return jsonify({'success': True, 'tools': tools})


# ============================================================================
# Workflow Routes (Protected)
# ============================================================================

#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/admin/workflows', methods=['GET', 'POST'])
@auth_service.require_auth
def admin_workflows(request:LambdaRequest):
    """List or create workflows"""
    if request.method == 'GET':
        workflows = workflow_service.list_workflows()
        return jsonify({'success': True, 'workflows': workflows})

    # POST - Create workflow
    try:
        data = request.body

        if not data:
            return jsonify({'error': 'No JSON data provided', 'success': False}), 400

        # Validate required fields
        if 'id' not in data or 'name' not in data:
            return jsonify({'error': 'Workflow ID and name are required', 'success': False}), 400

        # Set created_by from session
        user = auth_service.get_current_user()
        data['created_by'] = user['username'] if user else 'unknown'

        # Validate workflow configuration
        is_valid, errors = workflow_service.validate_workflow(data)
        if not is_valid:
            return jsonify({'error': 'Invalid workflow', 'errors': errors, 'success': False}), 400

        # Save workflow
        workflow = workflow_service.save_workflow(data)

        # Invalidate any cached compilation
        langgraph_service.invalidate_cache(data['id'])

        return jsonify({'workflow': workflow, 'success': True}), 201

    except Exception as e:
        logging.error(f"Error creating workflow: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/admin/workflows/<workflow_id>', methods=['GET', 'PUT', 'DELETE'])
@auth_service.require_auth
def admin_workflow(request:LambdaRequest):
    """Get, update, or delete a specific workflow"""
    workflow_id = request.args.get('workflow_id')
    if request.method == 'GET':
        workflow = workflow_service.get_workflow(workflow_id)
        if not workflow:
            return jsonify({'error': 'Workflow not found', 'success': False}), 404

        # Also return visualization data
        viz_data = langgraph_service.get_workflow_visualization(workflow_id)
        return jsonify({'workflow': workflow, 'visualization': viz_data, 'success': True})

    elif request.method == 'PUT':
        try:
            data = request.body

            if not data:
                return jsonify({'error': 'No JSON data provided', 'success': False}), 400

            data['id'] = workflow_id  # Ensure ID matches

            # Validate workflow configuration
            is_valid, errors = workflow_service.validate_workflow(data)
            if not is_valid:
                return jsonify({'error': 'Invalid workflow', 'errors': errors, 'success': False}), 400

            # Save workflow
            workflow = workflow_service.save_workflow(data)

            # Invalidate cached compilation
            langgraph_service.invalidate_cache(workflow_id)

            return jsonify({'workflow': workflow, 'success': True})

        except Exception as e:
            logging.error(f"Error updating workflow: {e}")
            return jsonify({'error': str(e), 'success': False}), 500

    elif request.method == 'DELETE':
        if workflow_service.delete_workflow(workflow_id):
            langgraph_service.invalidate_cache(workflow_id)
            return jsonify({'success': True, 'message': f'Workflow {workflow_id} deleted'})
        return jsonify({'error': 'Workflow not found', 'success': False}), 404


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/admin/workflows/<workflow_id>/validate', methods=['POST'])
@auth_service.require_auth
def validate_workflow(request:LambdaRequest):
    """Validate a workflow configuration"""
    try:
        workflow_id = request.args.get('workflow_id')
        data = request.body
        if not data:
            workflow = workflow_service.get_workflow(workflow_id)
            if not workflow:
                return jsonify({'error': 'Workflow not found', 'success': False}), 404
            data = workflow

        is_valid, errors = workflow_service.validate_workflow(data)
        return jsonify({
            'success': True,
            'valid': is_valid,
            'errors': errors
        })
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/admin/workflows/<workflow_id>/compile', methods=['POST'])
@auth_service.require_auth
def compile_workflow(request:LambdaRequest):
    """Compile a workflow and cache it"""
    try:
        workflow_id = request.args.get('workflow_id')
        workflow = workflow_service.get_workflow(workflow_id)
        if not workflow:
            return jsonify({'error': 'Workflow not found', 'success': False}), 404

        compiled = langgraph_service.compile_workflow(workflow)
        if compiled:
            return jsonify({'success': True, 'message': 'Workflow compiled successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to compile workflow'}), 500

    except Exception as e:
        logging.error(f"Error compiling workflow: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


# ============================================================================
# Workflow Chat Endpoints (Public for workflow execution)
# ============================================================================

#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/workflow/<workflow_id>/chat', methods=['POST'])
def workflow_chat_api( request:LambdaRequest):
    """Execute a workflow with user input"""
    try:
        workflow_id = request.args.get('workflow_id')
        workflow = workflow_service.get_workflow(workflow_id)
        if not workflow:
            return jsonify({'error': f'Workflow {workflow_id} not found', 'success': False}), 404

        data = request.body
        user_message = data.get('message', '')

        if not user_message:
            return jsonify({'error': 'No message provided', 'success': False}), 400

        # Initialize session context
        session_key = f'workflow_{workflow_id}_context'
        if session_key not in session:
            session[session_key] = {}

        session_context = session[session_key]

        # Execute workflow
        result = langgraph_service.execute_workflow(workflow_id, user_message, session_context)

        # Update session context
        if result.get('success'):
            session_context['conversation_history'] = result.get('messages', [])
            session_context['metadata'] = result.get('metadata', {})
            session[session_key] = session_context

        return jsonify(result)

    except Exception as e:
        logging.error(f"Error in workflow chat API: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing @app.route('/workflow/<workflow_id>/chat/stream', methods=['POST'])
def workflow_chat_stream_api(request:LambdaRequest):
    """Execute a workflow with streaming output"""
    try:
        workflow_id = request.args.get('workflow_id')
        workflow = workflow_service.get_workflow(workflow_id)
        if not workflow:
            return jsonify({'error': f'Workflow {workflow_id} not found', 'success': False}), 404

        data = request.body
        user_message = data.get('message', '')

        if not user_message:
            return jsonify({'error': 'No message provided', 'success': False}), 400

        # Initialize session context
        session_key = f'workflow_{workflow_id}_context'
        if session_key not in session:
            session[session_key] = {}

        session_context = session[session_key]

        def generate():
            for event in langgraph_service.execute_workflow_stream(workflow_id, user_message, session_context):
                event_data = json.dumps(event)
                yield f"data: {event_data}\n\n"

        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )

    except Exception as e:
        logging.error(f"Error in workflow stream API: {e}")
        return jsonify({'error': str(e), 'success': False}), 500


#TODO: Remove this line once Unit Testing done. This decorator not needed as This decorator not needed as Lambda handler will handles Routing:  @app.route('/workflow/<workflow_id>')
def workflow_chat(request:LambdaRequest):
    """Workflow chat interface"""
    workflow_id = request.args.get('workflow_id')
    workflow = workflow_service.get_workflow(workflow_id)
    if not workflow:
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": f"Workflow '{workflow_id}' not found"
        }

    # Generate default prompts based on workflow
    quick_prompts = [
        {'text': '💬 Start', 'prompt': 'Hello, I need help'},
        {'text': '❓ Help', 'prompt': 'What can you help me with?'}
    ]

    return render_template('index.html',
                           agent=workflow,
                           quick_prompts=quick_prompts,
                           is_workflow=True)


#if __name__ == '__main__':
   # app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)

