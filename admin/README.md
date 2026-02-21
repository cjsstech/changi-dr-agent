# Admin Console - Standalone Agent & Workflow Manager

A reusable admin interface for managing AI agents and visual multi-agent workflow builder using LangGraph.

## Features

- 🤖 **Agent Management** - Create, edit, delete AI agents
- 🔀 **Visual Workflow Builder** - Drag-and-drop multi-agent workflow design
- 📝 **Prompt Management** - Create and edit system prompts
- 🔧 **MCP Tools Integration** - Configure available tools for agents
- 🔐 **Simple Authentication** - Basic login protection

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables (Optional)

```bash
export OPENAI_API_KEY="your-openai-key"
export GOOGLE_API_KEY="your-google-key"
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="your-secure-password"
```

### 3. Run the Server

```bash
python app.py
```

### 4. Access the Admin Console

Open http://localhost:5050/admin and login with:
- Username: `admin`
- Password: `admin` (or your configured password)

## Project Structure

```
admin-console-standalone/
├── app.py                  # Main Flask application
├── config.py               # Configuration settings
├── requirements.txt        # Python dependencies
├── templates/
│   ├── admin.html         # Admin dashboard
│   └── login.html         # Login page
├── static/
│   ├── admin.css          # Admin styles
│   └── admin.js           # Admin JavaScript
├── agents/
│   ├── __init__.py
│   ├── agent_service.py   # Agent CRUD operations
│   ├── workflow_service.py # Workflow CRUD operations
│   └── langgraph_service.py # LangGraph integration
├── storage/
│   ├── agents.json        # Agent configurations
│   └── workflows.json     # Workflow configurations
└── prompts/
    └── example.txt        # Example prompt file
```

## Configuration

Edit `config.py` or use environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | - |
| `GOOGLE_API_KEY` | Google Gemini API key | - |
| `ADMIN_USERNAME` | Admin login username | `admin` |
| `ADMIN_PASSWORD` | Admin login password | `admin` |
| `PORT` | Server port | `5050` |
| `MCP_SERVER_URL` | MCP server endpoint | `http://localhost:8002/mcp` |

## Integrating with Your Project

1. Copy this folder to your project
2. Update `config.py` with your settings
3. Customize `get_available_tools()` in `app.py` for your MCP tools
4. Add your prompt files to `prompts/`
5. Integrate the agent executor with your LLM provider

## Workflow Builder

The swarm-style workflow builder allows you to:

1. **Add Nodes**: Click Orchestrator (👑) or Agent (🤖) buttons
2. **Position**: Drag nodes anywhere on the canvas
3. **Connect**: Drag from output port (right) to input port (left)
4. **Configure**: Click a node to select an agent
5. **Save**: The workflow is saved with all connections

## API Endpoints

### Agents
- `GET /admin/agents` - List all agents
- `POST /admin/agents` - Create agent
- `GET /admin/agents/<id>` - Get agent
- `PUT /admin/agents/<id>` - Update agent
- `DELETE /admin/agents/<id>` - Delete agent

### Workflows
- `GET /admin/workflows` - List all workflows
- `POST /admin/workflows` - Create workflow
- `GET /admin/workflows/<id>` - Get workflow
- `PUT /admin/workflows/<id>` - Update workflow
- `DELETE /admin/workflows/<id>` - Delete workflow

### Prompts
- `GET /admin/prompts` - List all prompts
- `GET /admin/prompts/<filename>` - Get prompt
- `PUT /admin/prompts/<filename>` - Update prompt
- `POST /admin/prompts` - Create prompt

## License

MIT License - Feel free to use and modify for your projects.
