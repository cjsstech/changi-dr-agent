# /admin/app.py

""" This Admin Web Application Controller"""

"""
Admin Console - Standalone Agent Management & Workflow Builder
A reusable admin interface for managing AI agents and multi-agent workflows.

This project can be used standalone or integrated into other AI agent applications.
"""
from core.web.app_tools import render_template, jsonify, session, redirect, url_for
from core.web.lambda_request import LambdaRequest
from functools import wraps
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Import services
from agents.agent_service import agent_service
from agents.workflow_service import workflow_service

# Try to import LangGraph service (optional)
try:
    from agents.langgraph_service import langgraph_service, LANGGRAPH_AVAILABLE
except ImportError:
    langgraph_service = None
    LANGGRAPH_AVAILABLE = False
    logger.warning("LangGraph not available - workflow execution disabled")

#app = Flask(__name__)
#app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'admin-console-secret-key-change-in-production')

# Configuration
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin')


# ============================================================================
# Authentication
# ============================================================================

def login_required(f, request:LambdaRequest):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)

    return decorated


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/login', methods=['GET', 'POST'])
def login(request:LambdaRequest):
    if request.method == 'POST':
        username = request.body.get('username')
        password = request.body.get('password')

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            logger.info(f"User {username} logged in")
            next_url = request.args.get('next', url_for('admin'))
            return redirect(next_url)
        else:
            return render_template('login.html', error='Invalid credentials')

    return render_template('login.html')


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/logout')
def logout(request:LambdaRequest):
    session.clear()
    return redirect(url_for('login'))


# ============================================================================
# Admin Dashboard
# ============================================================================

#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/admin')
@login_required
def admin():
    # Load available tools (customize based on your MCP tools)
    available_tools = get_available_tools()

    # Load prompt files
    prompt_files = get_prompt_files()

    return render_template('admin.html',
                           available_tools=available_tools,
                           prompt_files=prompt_files)


def get_available_tools():
    """Get list of available MCP tools - customize for your setup"""
    # Example tools - replace with your actual tool configuration
    return [
        {'id': 'flight_api', 'name': 'Flight API', 'description': 'Search and book flights', 'enabled': True},
        {'id': 'travel_content', 'name': 'Travel Content', 'description': 'Travel information and recommendations',
         'enabled': True},
        {'id': 'maps', 'name': 'Maps', 'description': 'Location and mapping services', 'enabled': True},
    ]


def get_prompt_files():
    """Get list of available prompt files"""
    prompts_dir = 'prompts'
    if os.path.exists(prompts_dir):
        return [f for f in os.listdir(prompts_dir) if f.endswith('.txt')]
    return []


# ============================================================================
# Agent CRUD API
# ============================================================================

#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/admin/agents', methods=['GET'])
@login_required
def get_agents():
    agents = agent_service.list_agents()
    return jsonify({'success': True, 'agents': agents})


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/admin/agents', methods=['POST'])
@login_required
def create_agent(request:LambdaRequest):
    try:
        agent_data = request.body
        agent = agent_service.save_agent(agent_data)
        return jsonify({'success': True, 'agent': agent})
    except Exception as e:
        logger.error(f"Error creating agent: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/admin/agents/<agent_id>', methods=['GET'])
@login_required
def get_agent(request:LambdaRequest):
    agent_id = request.args.get('agent_id')
    agent = agent_service.get_agent(agent_id)
    if agent:
        return jsonify({'success': True, 'agent': agent})
    return jsonify({'success': False, 'error': 'Agent not found'}), 404


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/admin/agents/<agent_id>', methods=['PUT'])
@login_required
def update_agent(request:LambdaRequest):
    try:
        agent_id = request.args.get('agent_id')
        agent_data = request.body
        agent_data['id'] = agent_id
        agent = agent_service.save_agent(agent_data)
        return jsonify({'success': True, 'agent': agent})
    except Exception as e:
        logger.error(f"Error updating agent: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/admin/agents/<agent_id>', methods=['DELETE'])
@login_required
def delete_agent(request:LambdaRequest):
    agent_id = request.args.get('agent_id')
    if agent_service.delete_agent(agent_id):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Agent not found'}), 404


# ============================================================================
# Workflow CRUD API
# ============================================================================

#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/admin/workflows', methods=['GET'])
@login_required
def get_workflows():
    workflows = workflow_service.list_workflows()
    return jsonify({'success': True, 'workflows': workflows})


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/admin/workflows', methods=['POST'])
@login_required
def create_workflow(request:LambdaRequest):
    try:
        workflow_data = request.body

        # Validate
        is_valid, errors = workflow_service.validate_workflow(workflow_data)
        if not is_valid:
            return jsonify({'success': False, 'error': 'Validation failed', 'errors': errors}), 400

        workflow = workflow_service.save_workflow(workflow_data)

        # Invalidate cache if LangGraph available
        if langgraph_service:
            langgraph_service.invalidate_cache(workflow['id'])

        return jsonify({'success': True, 'workflow': workflow})
    except Exception as e:
        logger.error(f"Error creating workflow: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/admin/workflows/<workflow_id>', methods=['GET'])
@login_required
def get_workflow(request:LambdaRequest):
    workflow_id = request.args.get('workflow_id')
    workflow = workflow_service.get_workflow(workflow_id)
    if workflow:
        viz = None
        if langgraph_service:
            viz = langgraph_service.get_workflow_visualization(workflow_id)
        return jsonify({'success': True, 'workflow': workflow, 'visualization': viz})
    return jsonify({'success': False, 'error': 'Workflow not found'}), 404


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/admin/workflows/<workflow_id>', methods=['PUT'])
@login_required
def update_workflow( request:LambdaRequest):
    try:
        workflow_id = request.args.get('workflow_id')
        workflow_data = request.body
        workflow_data['id'] = workflow_id

        is_valid, errors = workflow_service.validate_workflow(workflow_data)
        if not is_valid:
            return jsonify({'success': False, 'error': 'Validation failed', 'errors': errors}), 400

        workflow = workflow_service.save_workflow(workflow_data)

        if langgraph_service:
            langgraph_service.invalidate_cache(workflow_id)

        return jsonify({'success': True, 'workflow': workflow})
    except Exception as e:
        logger.error(f"Error updating workflow: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/admin/workflows/<workflow_id>', methods=['DELETE'])
@login_required
def delete_workflow(request:LambdaRequest):
    workflow_id = request.args.get('workflow_id')
    if workflow_service.delete_workflow(workflow_id):
        if langgraph_service:
            langgraph_service.invalidate_cache(workflow_id)
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Workflow not found'}), 404


# ============================================================================
# Prompts API
# ============================================================================

#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/admin/prompts', methods=['GET'])
@login_required
def get_prompts():
    prompts_dir = 'prompts'
    prompts = []

    if os.path.exists(prompts_dir):
        for filename in os.listdir(prompts_dir):
            if filename.endswith('.txt'):
                filepath = os.path.join(prompts_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                prompts.append({
                    'filename': filename,
                    'preview': content[:200] + '...' if len(content) > 200 else content,
                    'lines': len(content.split('\n')),
                    'chars': len(content)
                })

    return jsonify({'success': True, 'prompts': prompts})


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/admin/prompts/<filename>', methods=['GET', 'PUT'])
@login_required
def handle_prompt( request:LambdaRequest):
    filename = request.args.get('filename')
    filepath = os.path.join('prompts', filename)

    if request.method == 'GET':
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify({'success': True, 'prompt': {'filename': filename, 'content': content}})
        return jsonify({'success': False, 'error': 'Prompt not found'}), 404

    elif request.method == 'PUT':
        data = request.get_json()
        content = data.get('content', '')
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400


#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/admin/prompts', methods=['POST'])
@login_required
def create_prompt(request:LambdaRequest):

    data = request.body
    filename = data.get('filename', '').strip()
    content = data.get('content', '')

    if not filename:
        return jsonify({'success': False, 'error': 'Filename is required'}), 400

    if not filename.endswith('.txt'):
        filename += '.txt'

    filepath = os.path.join('prompts', filename)

    if os.path.exists(filepath):
        return jsonify({'success': False, 'error': 'File already exists'}), 400

    try:
        os.makedirs('prompts', exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# ============================================================================
# MCP Tools API
# ============================================================================

#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/admin/mcp/tools', methods=['GET'])
@login_required
def get_mcp_tools():
    tools = get_available_tools()
    return jsonify({'success': True, 'tools': tools})


# ============================================================================
# Index/Home
# ============================================================================

#TODO: Remove this line once Unit Testing done. This decorator not needed as Lambda handler will handles Routing: @app.route('/')
def index():
    return redirect(url_for('admin'))


# ============================================================================
# Run Server
# ============================================================================
# TODO Remove this code
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           Admin Console - Agent & Workflow Manager            ║
╠══════════════════════════════════════════════════════════════╣
║  URL:      http://localhost:{port}/admin                        ║
║  Login:    {ADMIN_USERNAME} / {ADMIN_PASSWORD}                                     ║
╚══════════════════════════════════════════════════════════════╝
    """)

    #app.run(host='0.0.0.0', port=port, debug=debug)
