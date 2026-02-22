// Admin UI JavaScript
let currentEditingId = null;
let currentEditingPrompt = null;

// API base URL (stage prefix injected from admin.html)
const apiBase = (typeof API_BASE !== 'undefined') ? API_BASE : '';

// Available models by provider
const AVAILABLE_MODELS = {
    openai: [
        { value: 'gpt-4o', label: 'GPT-4o (Most capable, multimodal)' },
        { value: 'gpt-4o-mini', label: 'GPT-4o Mini (Faster, cheaper)' },
        { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
        { value: 'gpt-4', label: 'GPT-4' },
        { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
        { value: 'o1', label: 'O1 (Reasoning model)' },
        { value: 'o1-mini', label: 'O1 Mini (Reasoning, smaller)' }
    ],
    gemini: [
        { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (Cheaper, Fast)' },
        { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro (Most Capable)' },
        { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
        { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash (Fast, Efficient)' },
        { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro (Most Capable)' },
        { value: 'gemini-2.0-flash-exp', label: 'Gemini 2.0 Flash (Experimental)' },
        { value: 'gemini-pro', label: 'Gemini Pro (Legacy)' }
    ]
};

// Load on page load
document.addEventListener('DOMContentLoaded', function () {
    loadAgents();
    loadPrompts();
    loadMCPTools();
    loadWorkflows();
    setupFormHandlers();
    setupProviderChangeHandler();
    setupTabNavigation();
    updateModelDropdown('openai');
    setupWorkflowFormHandler();
});

// ============================================================================
// Tab Navigation
// ============================================================================

function setupTabNavigation() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            const tabId = this.dataset.tab;
            switchTab(tabId);
        });
    });
}

function switchTab(tabId) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `${tabId}-tab`);
    });
}

// ============================================================================
// Overview Cards
// ============================================================================

function updateOverviewCounts(agents, prompts, tools) {
    document.getElementById('agentsCount').textContent = agents || 0;
    document.getElementById('promptsCount').textContent = prompts || 0;
    document.getElementById('toolsCount').textContent = tools || 0;
}

// ============================================================================
// Agents Management
// ============================================================================

function loadAgents() {
    fetch(`${apiBase}/admin/agents`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayAgents(data.agents);
                // Update overview count
                document.getElementById('agentsCount').textContent = data.agents.length;
            } else {
                console.error('Error loading agents:', data.error);
            }
        })
        .catch(error => {
            console.error('Error loading agents:', error);
        });
}

function displayAgents(agents) {
    const agentsList = document.getElementById('agentsList');

    if (agents.length === 0) {
        agentsList.innerHTML = `
            <div class="empty-state">
                <p>No agents created yet.</p>
                <p>Create your first agent using the form on the right.</p>
            </div>
        `;
        return;
    }

    agentsList.innerHTML = agents.map(agent => `
        <div class="agent-card">
            <div class="agent-card-header">
                <h3>${escapeHtml(agent.name)}</h3>
                <div class="agent-card-actions">
                    <button class="btn-small btn-edit" onclick="editAgent('${agent.id}')">Edit</button>
                    <button class="btn-small btn-test" onclick="testAgent('${agent.id}')">Test</button>
                    <button class="btn-small btn-delete" onclick="deleteAgent('${agent.id}')">Delete</button>
                </div>
            </div>
            <p>${escapeHtml(agent.description || 'No description')}</p>
            <div class="agent-card-meta">
                <span>Provider: ${agent.llm_provider}</span>
                <span>Model: ${agent.llm_model}</span>
                <span>Tools: ${agent.mcp_tools?.length || 0}</span>
            </div>
        </div>
    `).join('');
}

function setupFormHandlers() {
    const form = document.getElementById('agentForm');
    const cancelBtn = document.getElementById('cancelBtn');

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        saveAgent();
    });

    cancelBtn.addEventListener('click', function () {
        resetForm();
    });
}

function setupProviderChangeHandler() {
    const providerSelect = document.getElementById('llmProvider');
    providerSelect.addEventListener('change', function () {
        updateModelDropdown(this.value);
    });
}

function updateModelDropdown(provider) {
    const modelSelect = document.getElementById('llmModel');
    const models = AVAILABLE_MODELS[provider] || [];

    // Clear existing options
    modelSelect.innerHTML = '';

    // Add options for the selected provider
    models.forEach(model => {
        const option = document.createElement('option');
        option.value = model.value;
        option.textContent = model.label;
        modelSelect.appendChild(option);
    });
}

function saveAgent() {
    const form = document.getElementById('agentForm');
    const formData = new FormData(form);

    // Get form values
    const promptFile = document.getElementById('promptFile').value;
    const systemPrompt = document.getElementById('systemPrompt').value;

    const agentData = {
        id: document.getElementById('agentId').value || generateAgentId(),
        name: document.getElementById('agentName').value,
        description: document.getElementById('agentDescription').value,
        llm_provider: document.getElementById('llmProvider').value,
        llm_model: document.getElementById('llmModel').value,
        mcp_tools: Array.from(document.querySelectorAll('input[name="mcp_tools"]:checked')).map(cb => cb.value)
    };

    // Add prompt_file or system_prompt (at least one required)
    if (promptFile) {
        agentData.prompt_file = promptFile;
    }
    if (systemPrompt) {
        agentData.system_prompt = systemPrompt;
    }

    // Validate
    if (!agentData.name || !agentData.llm_model) {
        alert('Please fill in all required fields');
        return;
    }

    if (!agentData.prompt_file && !agentData.system_prompt) {
        alert('Please either select a prompt file or enter a system prompt');
        return;
    }

    const url = currentEditingId
        ? `${apiBase}/admin/agents/${currentEditingId}`
        : `${apiBase}/admin/agents`;

    const method = currentEditingId ? 'PUT' : 'POST';

    fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(agentData)
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Agent saved successfully!');
                resetForm();
                loadAgents();
            } else {
                alert('Error saving agent: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error saving agent:', error);
            alert('Error saving agent: ' + error.message);
        });
}

function editAgent(agentId) {
    fetch(`${apiBase}/admin/agents/${agentId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const agent = data.agent;
                currentEditingId = agent.id;

                document.getElementById('agentId').value = agent.id;
                document.getElementById('agentName').value = agent.name;
                document.getElementById('agentDescription').value = agent.description || '';

                // Set provider first, then update model dropdown
                document.getElementById('llmProvider').value = agent.llm_provider;
                updateModelDropdown(agent.llm_provider);

                // Set model after dropdown is updated
                setTimeout(() => {
                    const modelSelect = document.getElementById('llmModel');
                    modelSelect.value = agent.llm_model;
                    // If model not in dropdown, add it as custom option
                    if (!modelSelect.value && agent.llm_model) {
                        const option = document.createElement('option');
                        option.value = agent.llm_model;
                        option.textContent = agent.llm_model + ' (custom)';
                        option.selected = true;
                        modelSelect.appendChild(option);
                    }
                }, 10);

                // Set prompt file or system prompt
                if (agent.prompt_file) {
                    document.getElementById('promptFile').value = agent.prompt_file;
                    document.getElementById('systemPrompt').value = '';
                    document.getElementById('promptRequired').style.display = 'none';
                } else {
                    document.getElementById('promptFile').value = '';
                    document.getElementById('systemPrompt').value = agent.system_prompt || '';
                    document.getElementById('promptRequired').style.display = 'inline';
                }

                // Set MCP tools checkboxes
                document.querySelectorAll('input[name="mcp_tools"]').forEach(cb => {
                    cb.checked = (agent.mcp_tools || []).includes(cb.value);
                });

                document.getElementById('formTitle').textContent = 'Edit Agent';
                document.getElementById('cancelBtn').style.display = 'inline-block';

                // Scroll to form
                document.querySelector('.agent-form-section').scrollIntoView({ behavior: 'smooth' });
            } else {
                alert('Error loading agent: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error loading agent:', error);
            alert('Error loading agent: ' + error.message);
        });
}

function deleteAgent(agentId) {
    if (!confirm('Are you sure you want to delete this agent?')) {
        return;
    }

    fetch(`${apiBase}/admin/agents/${agentId}`, {
        method: 'DELETE'
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Agent deleted successfully!');
                loadAgents();
                if (currentEditingId === agentId) {
                    resetForm();
                }
            } else {
                alert('Error deleting agent: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error deleting agent:', error);
            alert('Error deleting agent: ' + error.message);
        });
}

function testAgent(agentId) {
    window.open(`${apiBase}/agent/${agentId}`, '_blank');
}

function resetForm() {
    document.getElementById('agentForm').reset();
    document.getElementById('agentId').value = '';
    currentEditingId = null;
    document.getElementById('formTitle').textContent = 'Create New Agent';
    document.getElementById('cancelBtn').style.display = 'none';
    // Reset model dropdown to OpenAI defaults
    updateModelDropdown('openai');
    // Show prompt required indicator
    document.getElementById('promptRequired').style.display = 'inline';
}

// Handle prompt file selection
document.addEventListener('DOMContentLoaded', function () {
    const promptFileSelect = document.getElementById('promptFile');
    const systemPromptTextarea = document.getElementById('systemPrompt');
    const promptRequired = document.getElementById('promptRequired');

    if (promptFileSelect && systemPromptTextarea) {
        promptFileSelect.addEventListener('change', function () {
            if (this.value) {
                // Prompt file selected - make system prompt optional
                systemPromptTextarea.required = false;
                promptRequired.style.display = 'none';
            } else {
                // No prompt file - system prompt is required
                systemPromptTextarea.required = true;
                promptRequired.style.display = 'inline';
            }
        });
    }
});

function generateAgentId() {
    return 'agent-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// Prompts Management
// ============================================================================

function loadPrompts() {
    fetch(`${apiBase}/admin/prompts`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayPrompts(data.prompts);
                document.getElementById('promptsCount').textContent = data.prompts.length;
            } else {
                console.error('Error loading prompts:', data.error);
            }
        })
        .catch(error => {
            console.error('Error loading prompts:', error);
        });
}

function displayPrompts(prompts) {
    const promptsList = document.getElementById('promptsList');

    if (prompts.length === 0) {
        promptsList.innerHTML = `
            <div class="empty-state">
                <p>No prompts found.</p>
                <p>Create your first prompt using the button above.</p>
            </div>
        `;
        return;
    }

    promptsList.innerHTML = prompts.map(prompt => `
        <div class="prompt-card">
            <div class="prompt-card-header">
                <h3>📄 ${escapeHtml(prompt.filename)}</h3>
                <div class="prompt-card-actions">
                    <button class="btn-small btn-edit" onclick="editPrompt('${escapeHtml(prompt.filename)}')">Edit</button>
                </div>
            </div>
            <p class="prompt-preview">${escapeHtml(prompt.preview)}</p>
            <div class="prompt-card-meta">
                <span>${prompt.lines} lines</span>
                <span>${prompt.chars} characters</span>
            </div>
        </div>
    `).join('');
}

function editPrompt(filename) {
    currentEditingPrompt = filename;

    fetch(`${apiBase}/admin/prompt?file_name=${encodeURIComponent(filename)}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('promptEditorTitle').textContent = `Edit: ${filename}`;
                document.getElementById('promptFileName').value = filename;
                document.getElementById('promptContent').value = data.prompt.content;
                document.getElementById('newPromptNameGroup').style.display = 'none';
                document.getElementById('promptEditorSection').style.display = 'block';
                document.getElementById('promptEditorSection').scrollIntoView({ behavior: 'smooth' });
            } else {
                alert('Error loading prompt: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error loading prompt:', error);
            alert('Error loading prompt: ' + error.message);
        });
}

function showCreatePromptForm() {
    currentEditingPrompt = null;
    document.getElementById('promptEditorTitle').textContent = 'Create New Prompt';
    document.getElementById('promptFileName').value = '';
    document.getElementById('newPromptName').value = '';
    document.getElementById('promptContent').value = '';
    document.getElementById('newPromptNameGroup').style.display = 'block';
    document.getElementById('promptEditorSection').style.display = 'block';
    document.getElementById('promptEditorSection').scrollIntoView({ behavior: 'smooth' });
}

function hidePromptEditor() {
    document.getElementById('promptEditorSection').style.display = 'none';
    currentEditingPrompt = null;
}

function setupPromptFormHandler() {
    const promptForm = document.getElementById('promptForm');
    if (promptForm) {
        promptForm.addEventListener('submit', function (e) {
            e.preventDefault();
            savePrompt();
        });
    }
}

function savePrompt() {
    const content = document.getElementById('promptContent').value;

    if (!content.trim()) {
        alert('Please enter prompt content');
        return;
    }

    if (currentEditingPrompt) {
        // Update existing prompt
        fetch(`${apiBase}/admin/prompt?file_name=${encodeURIComponent(currentEditingPrompt)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Prompt saved successfully!');
                    hidePromptEditor();
                    loadPrompts();
                } else {
                    alert('Error saving prompt: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error saving prompt:', error);
                alert('Error saving prompt: ' + error.message);
            });
    } else {
        // Create new prompt
        const filename = document.getElementById('newPromptName').value;
        if (!filename.trim()) {
            alert('Please enter a filename');
            return;
        }

        fetch(`${apiBase}/admin/prompts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename, content })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Prompt created successfully!');
                    hidePromptEditor();
                    loadPrompts();
                } else {
                    alert('Error creating prompt: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error creating prompt:', error);
                alert('Error creating prompt: ' + error.message);
            });
    }
}

// ============================================================================
// MCP Tools Display
// ============================================================================

function loadMCPTools() {
    fetch(`${apiBase}/admin/mcp/tools`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayMCPTools(data.tools);
                renderMCPToolGroups(data.tools); // Update tool selection list
                const enabledCount = groupMCPTools(data.tools).filter(t => t.enabled).length;
                document.getElementById('toolsCount').textContent = enabledCount;
            } else {
                console.error('Error loading MCP tools:', data.error);
            }
        })
        .catch(error => {
            console.error('Error loading MCP tools:', error);
        });
}

function renderMCPToolGroups(tools) {
    const container = document.getElementById('mcp_tools_list');
    const groups = groupMCPTools(tools);
    const enabledGroups = groups.filter(g => g.enabled);
    container.innerHTML = enabledGroups.map(g => `
        <label class="checkbox-label">
            <input type="checkbox" name="mcp_tools" value="${g.group_id}">
            <span>${getToolGroupName(g.group_id)}</span>
            <small>${getToolGroupDesc(g.group_id)}</small>
        </label>
    `).join('');
}

function displayMCPTools(tools) {
    console.log(tools);
    const toolsList = document.getElementById('mcpToolsList');
    const toolGroups = groupMCPTools(tools);
    toolsList.innerHTML = toolGroups.map(tool_group => `
        <div class="mcp-tool-card ${tool_group.enabled ? 'enabled' : 'disabled'}">
            <div class="mcp-tool-header">
                <span class="mcp-tool-icon">${getToolGroupIcon(tool_group.group_id)}</span>

                <h3>${getToolGroupName(tool_group.group_id)}</h3>
                <span class="mcp-tool-status ${tool_group.enabled ? 'status-enabled' : 'status-disabled'}">
                    ${tool_group.enabled ? '✓ Enabled' : '✗ Disabled'}
                </span>
            </div>

            <p class="mcp-tool-description">${getToolGroupDesc(tool_group.group_id)}</p>

            <div class="mcp-tool-id">
                <div class="mcp-tool-id-label">Tools:</div>
                <div class="mcp-tool-id-list">
                    ${tool_group.tool_names.map(t => `<code>${escapeHtml(t)}</code><br>`).join('')}
                </div>
                </div>
            </div>
    `).join('');
}

function getToolGroupIcon(tool_group) {
    const icons = {
        'flights': '✈️',
        'travel_content': '🌍',
        'nowboarding': '📰',
        'maps': '🗺️',
        'visa': '🛂',
        'browser': '🌐',
        'filesystem': '📁',
        'database': '💾'
    };
    return icons[tool_group] || '🔧';
}

function getToolGroupDesc(tool_group) {
    const descriptions = {
        'flights': 'Search and format flights from Changi Airport API',
        'travel_content': 'Generate booking links and guide pages for Lonely Planet and Trip.com',
        'nowboarding': 'The ONLY source for travel articles, stories, blogs, and reading material.',
        'maps': 'Geocode locations and generate map URLs',
        'visa': 'Visa requirements and visa information',
        'browser': 'Web navigation, screenshots, and page interaction',
        'filesystem': 'Read and write files',
        'database': 'Query databases'
    };
    return descriptions[tool_group] || 'No description available';
}

function getToolGroupName(tool_group) {
    const names = {
        'flights': 'Flights',
        'travel_content': 'Travel Content',
        'nowboarding': 'Now Boarding Articles',
        'maps': 'Maps & Geocoding',
        'visa': 'Visa Requirements',
        'browser': 'Browser',
        'filesystem': 'File System',
        'database': 'Database'
    };
    return names[tool_group] || 'Unknown';
}

const UPCOMING_TOOL_GROUPS = {
    browser: {
        group_id: "browser",
        name: "Browser",
        description: "Web navigation, screenshots, and page interaction",
        enabled: false,
        tool_names: []
    },
    filesystem: {
        group_id: "filesystem",
        name: "File System",
        description: "Read and write files",
        enabled: false,
        tool_names: []
    },
    database: {
        group_id: "database",
        name: "Database",
        description: "Query databases",
        enabled: false,
        tool_names: []
    }
};
function groupMCPTools(tools) {
    const groups = {};
    tools.forEach(tool => {
        const [groupId, subName] = tool.name.split('.', 2);
        if (!groups[groupId]) {
            groups[groupId] = {
                group_id: groupId,
                enabled: true,   // group exists → enabled
                tool_names: []
            };
        }
        groups[groupId].tool_names.push(tool.name);
    });
    Object.values(UPCOMING_TOOL_GROUPS).forEach(upcomingGroup => {
        if (!groups[upcomingGroup.group_id]) {
            groups[upcomingGroup.group_id] = { ...upcomingGroup };
        }
    });
    return Object.values(groups);
}
// Initialize prompt form handler after DOM loaded
document.addEventListener('DOMContentLoaded', function () {
    setupPromptFormHandler();
});

document.addEventListener("DOMContentLoaded", () => { renderMCPToolGroups(mcpTools); });

// ============================================================================
// Workflows Management
// ============================================================================

let currentEditingWorkflowId = null;
let workflowNodes = [];
let workflowEdges = [];
let selectedNodeId = null;
let nodeIdCounter = 0;
let availableAgentsList = [];

function loadWorkflows() {
    fetch(`${apiBase}/admin/workflows`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayWorkflows(data.workflows);
            } else {
                console.error('Error loading workflows:', data.error);
            }
        })
        .catch(error => {
            console.error('Error loading workflows:', error);
        });

    // Also load agents for the workflow builder
    fetch(`${apiBase}/admin/agents`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                availableAgentsList = data.agents;
            }
        });
}

function displayWorkflows(workflows) {
    const workflowsList = document.getElementById('workflowsList');

    if (!workflows || workflows.length === 0) {
        workflowsList.innerHTML = `
            <div class="empty-state">
                <p>🔀 No workflows created yet.</p>
                <p>Click "+ New Workflow" to create your first multi-agent workflow.</p>
            </div>
        `;
        return;
    }

    workflowsList.innerHTML = workflows.map(workflow => `
        <div class="workflow-card">
            <div class="workflow-card-header">
                <h3>🔀 ${escapeHtml(workflow.name)}</h3>
                <div class="workflow-card-actions">
                    <button class="btn-small btn-edit" onclick="editWorkflow('${workflow.id}')">Edit</button>
                    <button class="btn-small btn-test" onclick="testWorkflow('${workflow.id}')">Test</button>
                    <button class="btn-small btn-delete" onclick="deleteWorkflow('${workflow.id}')">Delete</button>
                </div>
            </div>
            <p>${escapeHtml(workflow.description || 'No description')}</p>
            <div class="workflow-card-stats">
                <span class="workflow-stat">📍 <strong>${(workflow.nodes || []).length}</strong> nodes</span>
                <span class="workflow-stat">🔗 <strong>${(workflow.edges || []).length}</strong> edges</span>
            </div>
        </div>
    `).join('');
}

function showCreateWorkflowForm() {
    currentEditingWorkflowId = null;
    workflowNodes = [];
    workflowEdges = [];
    nodeIdCounter = 0;

    document.getElementById('workflowEditorTitle').textContent = 'Create New Workflow';
    document.getElementById('workflowId').value = '';
    document.getElementById('workflowName').value = '';
    document.getElementById('workflowDescription').value = '';

    clearWorkflowCanvas();
    document.getElementById('workflowEditorSection').style.display = 'block';
    document.getElementById('workflowEditorSection').scrollIntoView({ behavior: 'smooth' });
}

function hideWorkflowEditor() {
    document.getElementById('workflowEditorSection').style.display = 'none';
    currentEditingWorkflowId = null;
}

function editWorkflow(workflowId) {
    fetch(`${apiBase}/admin/workflow?workflow_id=${workflowId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const workflow = data.workflow;
                currentEditingWorkflowId = workflow.id;

                document.getElementById('workflowEditorTitle').textContent = `Edit: ${workflow.name}`;
                document.getElementById('workflowId').value = workflow.id;
                document.getElementById('workflowName').value = workflow.name;
                document.getElementById('workflowDescription').value = workflow.description || '';

                workflowNodes = workflow.nodes || [];
                workflowEdges = workflow.edges || [];

                nodeIdCounter = 0;
                workflowNodes.forEach(node => {
                    const match = node.id.match(/node-(\d+)/);
                    if (match) nodeIdCounter = Math.max(nodeIdCounter, parseInt(match[1]));
                });

                renderWorkflowCanvas();
                document.getElementById('workflowEditorSection').style.display = 'block';
                document.getElementById('workflowEditorSection').scrollIntoView({ behavior: 'smooth' });
            } else {
                alert('Error loading workflow: ' + data.error);
            }
        });
}

function deleteWorkflow(workflowId) {
    if (!confirm('Are you sure you want to delete this workflow?')) return;

    fetch(`${apiBase}/admin/workflow?workflow_id=${workflowId}`, { method: 'DELETE' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Workflow deleted successfully!');
                loadWorkflows();
                if (currentEditingWorkflowId === workflowId) hideWorkflowEditor();
            } else {
                alert('Error deleting workflow: ' + data.error);
            }
        });
}

function testWorkflow(workflowId) {
    window.open(`${apiBase}/workflow?workflow_id=${workflowId}`, '_blank');
}

function setupWorkflowFormHandler() {
    const workflowForm = document.getElementById('workflowForm');
    if (workflowForm) {
        workflowForm.addEventListener('submit', function (e) {
            e.preventDefault();
            saveWorkflow();
        });
    }
}

function saveWorkflow() {
    const name = document.getElementById('workflowName').value.trim();
    if (!name) { alert('Please enter a workflow name'); return; }

    if (workflowNodes.length === 0) {
        alert('Please add at least one agent to the workflow');
        return;
    }

    // Check if agents are configured
    const unconfiguredAgents = workflowNodes.filter(n => (n.type === 'agent' || n.type === 'orchestrator') && !n.agent_id);
    if (unconfiguredAgents.length > 0) {
        alert('Please select an agent for all nodes');
        return;
    }

    const workflowData = {
        id: currentEditingWorkflowId || ('workflow-' + Date.now()),
        name: name,
        description: document.getElementById('workflowDescription').value.trim(),
        nodes: workflowNodes,
        edges: workflowEdges
    };

    const url = currentEditingWorkflowId ? `${apiBase}/admin/workflows?workflow_id=${currentEditingWorkflowId}` : `${apiBase}/admin/workflows`;

    fetch(url, {
        method: currentEditingWorkflowId ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(workflowData)
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Workflow saved successfully!');
                hideWorkflowEditor();
                loadWorkflows();
            } else {
                alert('Error saving workflow: ' + (data.error || 'Unknown error'));
            }
        });
}

function clearWorkflowCanvas() {
    workflowNodes = [];
    workflowEdges = [];
    selectedNodeId = null;
    connectingFromNode = null;
    renderWorkflowCanvas();
    const panel = document.getElementById('nodePropertiesPanel');
    if (panel) panel.style.display = 'none';
}

// Connection state
let connectingFromNode = null;
let isDraggingNode = false;
let dragOffset = { x: 0, y: 0 };
let draggingNodeId = null;

function renderWorkflowCanvas() {
    const canvas = document.getElementById('workflowCanvas');
    const placeholder = document.getElementById('canvasPlaceholder');
    const svg = document.getElementById('workflowEdgesSvg');

    if (workflowNodes.length === 0) {
        if (placeholder) placeholder.style.display = 'block';
        if (svg) svg.innerHTML = '';
        // Remove any existing nodes
        canvas.querySelectorAll('.workflow-node').forEach(n => n.remove());
        return;
    }

    if (placeholder) placeholder.style.display = 'none';

    // Build nodes HTML
    let nodesHtml = '';
    workflowNodes.forEach(node => {
        const pos = node.position || { x: 50, y: 50 };
        const isOrchestrator = node.type === 'orchestrator';
        const icon = isOrchestrator ? '👑' : '🤖';
        const agent = availableAgentsList.find(a => a.id === node.agent_id);
        const label = agent ? agent.name : (isOrchestrator ? 'Orchestrator' : 'Agent');
        const nodeClass = isOrchestrator ? 'orchestrator-node' : 'agent-node';

        nodesHtml += `
            <div class="workflow-node ${nodeClass} ${selectedNodeId === node.id ? 'selected' : ''}" 
                 style="left:${pos.x}px; top:${pos.y}px;" 
                 data-node-id="${node.id}"
                 onmousedown="onNodeMouseDown(event, '${node.id}')"
                 onclick="selectNode('${node.id}')">
                <div class="node-header">
                    <span class="node-icon">${icon}</span>
                    <span class="node-label">${escapeHtml(label)}</span>
                </div>
                ${!agent ? '<div class="node-subtitle">(click to configure)</div>' : ''}
                <div class="node-port input" data-port="input" data-node="${node.id}"
                     onmouseup="onPortMouseUp(event, '${node.id}', 'input')"></div>
                <div class="node-port output" data-port="output" data-node="${node.id}"
                     onmousedown="onPortMouseDown(event, '${node.id}', 'output')"></div>
                <button class="node-delete" onclick="event.stopPropagation(); deleteNode('${node.id}')">×</button>
            </div>
        `;
    });

    // Update canvas - keep SVG, update nodes
    canvas.querySelectorAll('.workflow-node').forEach(n => n.remove());
    canvas.insertAdjacentHTML('beforeend', nodesHtml);

    // Render edges
    renderEdges();
}

function renderEdges() {
    const svg = document.getElementById('workflowEdgesSvg');
    if (!svg) return;

    let pathsHtml = '';

    workflowEdges.forEach(edge => {
        const sourceNode = document.querySelector(`[data-node-id="${edge.source}"]`);
        const targetNode = document.querySelector(`[data-node-id="${edge.target}"]`);

        if (sourceNode && targetNode) {
            const sourcePort = sourceNode.querySelector('.node-port.output');
            const targetPort = targetNode.querySelector('.node-port.input');

            if (sourcePort && targetPort) {
                const canvas = document.getElementById('workflowCanvas');
                const canvasRect = canvas.getBoundingClientRect();

                const sourceRect = sourcePort.getBoundingClientRect();
                const targetRect = targetPort.getBoundingClientRect();

                const x1 = sourceRect.left - canvasRect.left + sourceRect.width / 2;
                const y1 = sourceRect.top - canvasRect.top + sourceRect.height / 2;
                const x2 = targetRect.left - canvasRect.left + targetRect.width / 2;
                const y2 = targetRect.top - canvasRect.top + targetRect.height / 2;

                // Bezier curve for smooth edges
                const midX = (x1 + x2) / 2;
                const path = `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`;

                pathsHtml += `<path d="${path}" data-source="${edge.source}" data-target="${edge.target}"/>`;
            }
        }
    });

    svg.innerHTML = pathsHtml;
}

function addWorkflowNode(type) {
    nodeIdCounter++;

    // Calculate position - spread nodes across canvas
    const baseX = 80 + (workflowNodes.length % 4) * 200;
    const baseY = 80 + Math.floor(workflowNodes.length / 4) * 120;

    const newNode = {
        id: `node-${nodeIdCounter}`,
        type: type,
        position: { x: baseX, y: baseY },
        agent_id: ''
    };

    workflowNodes.push(newNode);
    renderWorkflowCanvas();
    selectNode(newNode.id);
}

function deleteNode(nodeId) {
    workflowNodes = workflowNodes.filter(n => n.id !== nodeId);
    workflowEdges = workflowEdges.filter(e => e.source !== nodeId && e.target !== nodeId);
    if (selectedNodeId === nodeId) {
        selectedNodeId = null;
        const panel = document.getElementById('nodePropertiesPanel');
        if (panel) panel.style.display = 'none';
    }
    renderWorkflowCanvas();
}

function selectNode(nodeId) {
    selectedNodeId = nodeId;
    renderWorkflowCanvas();
    showNodeProperties(nodeId);
}

function showNodeProperties(nodeId) {
    const node = workflowNodes.find(n => n.id === nodeId);
    if (!node) return;

    const panel = document.getElementById('nodePropertiesPanel');
    const content = document.getElementById('nodePropertiesContent');
    if (!panel || !content) return;

    const isOrchestrator = node.type === 'orchestrator';
    let html = `<p><strong>Type:</strong> ${isOrchestrator ? '👑 Orchestrator' : '🤖 Agent'}</p>`;

    html += `<div class="form-group"><label>Select Agent</label>
        <select onchange="updateNodeAgent('${nodeId}', this.value)">
        <option value="">-- Select an agent --</option>
        ${availableAgentsList.map(a => `<option value="${a.id}" ${node.agent_id === a.id ? 'selected' : ''}>${escapeHtml(a.name)}</option>`).join('')}
        </select></div>`;

    // Show connections
    const outgoingEdges = workflowEdges.filter(e => e.source === nodeId);
    const incomingEdges = workflowEdges.filter(e => e.target === nodeId);

    if (outgoingEdges.length > 0) {
        html += '<p style="margin-top:10px"><strong>Outputs to:</strong></p><ul style="font-size:13px">';
        outgoingEdges.forEach(e => {
            const targetNode = workflowNodes.find(n => n.id === e.target);
            const agent = targetNode ? availableAgentsList.find(a => a.id === targetNode.agent_id) : null;
            const name = agent ? agent.name : e.target;
            html += `<li>→ ${escapeHtml(name)} <button onclick="removeEdge('${e.source}','${e.target}')" style="font-size:10px; margin-left:5px">×</button></li>`;
        });
        html += '</ul>';
    }

    if (incomingEdges.length > 0) {
        html += '<p style="margin-top:10px"><strong>Inputs from:</strong></p><ul style="font-size:13px">';
        incomingEdges.forEach(e => {
            const sourceNode = workflowNodes.find(n => n.id === e.source);
            const agent = sourceNode ? availableAgentsList.find(a => a.id === sourceNode.agent_id) : null;
            const name = agent ? agent.name : e.source;
            html += `<li>← ${escapeHtml(name)}</li>`;
        });
        html += '</ul>';
    }

    content.innerHTML = html;
    panel.style.display = 'block';
}

function updateNodeAgent(nodeId, agentId) {
    const node = workflowNodes.find(n => n.id === nodeId);
    if (node) {
        node.agent_id = agentId;
        renderWorkflowCanvas();
        showNodeProperties(nodeId);
    }
}

function addEdge(sourceId, targetId) {
    if (!targetId || sourceId === targetId) return;
    if (workflowEdges.some(e => e.source === sourceId && e.target === targetId)) return;
    workflowEdges.push({ source: sourceId, target: targetId });
    renderWorkflowCanvas();
    if (selectedNodeId) showNodeProperties(selectedNodeId);
}

function removeEdge(sourceId, targetId) {
    workflowEdges = workflowEdges.filter(e => !(e.source === sourceId && e.target === targetId));
    renderWorkflowCanvas();
    if (selectedNodeId) showNodeProperties(selectedNodeId);
}

// Node dragging
function onNodeMouseDown(event, nodeId) {
    if (event.target.classList.contains('node-port') || event.target.classList.contains('node-delete')) return;

    isDraggingNode = true;
    draggingNodeId = nodeId;

    const nodeEl = document.querySelector(`[data-node-id="${nodeId}"]`);
    if (nodeEl) {
        const rect = nodeEl.getBoundingClientRect();
        dragOffset.x = event.clientX - rect.left;
        dragOffset.y = event.clientY - rect.top;
        nodeEl.classList.add('dragging');
    }

    document.addEventListener('mousemove', onNodeMouseMove);
    document.addEventListener('mouseup', onNodeMouseUp);
    event.preventDefault();
}

function onNodeMouseMove(event) {
    if (!isDraggingNode || !draggingNodeId) return;

    const canvas = document.getElementById('workflowCanvas');
    const canvasRect = canvas.getBoundingClientRect();

    const x = Math.max(0, event.clientX - canvasRect.left - dragOffset.x);
    const y = Math.max(0, event.clientY - canvasRect.top - dragOffset.y);

    const nodeEl = document.querySelector(`[data-node-id="${draggingNodeId}"]`);
    if (nodeEl) {
        nodeEl.style.left = x + 'px';
        nodeEl.style.top = y + 'px';
    }

    // Update node position in data
    const node = workflowNodes.find(n => n.id === draggingNodeId);
    if (node) {
        node.position = { x, y };
    }

    // Re-render edges
    renderEdges();
}

function onNodeMouseUp(event) {
    if (draggingNodeId) {
        const nodeEl = document.querySelector(`[data-node-id="${draggingNodeId}"]`);
        if (nodeEl) nodeEl.classList.remove('dragging');
    }

    isDraggingNode = false;
    draggingNodeId = null;
    document.removeEventListener('mousemove', onNodeMouseMove);
    document.removeEventListener('mouseup', onNodeMouseUp);
}

// Port-based connections
function onPortMouseDown(event, nodeId, portType) {
    if (portType === 'output') {
        connectingFromNode = nodeId;
        document.getElementById('workflowCanvas').classList.add('connecting');
    }
    event.stopPropagation();
}

function onPortMouseUp(event, nodeId, portType) {
    if (portType === 'input' && connectingFromNode && connectingFromNode !== nodeId) {
        addEdge(connectingFromNode, nodeId);
    }
    connectingFromNode = null;
    document.getElementById('workflowCanvas').classList.remove('connecting');
    event.stopPropagation();
}

// Canvas events for drag-drop
function onCanvasDragOver(event) {
    event.preventDefault();
}

function onCanvasDrop(event) {
    event.preventDefault();
}

// Auto-layout function
function autoLayout() {
    if (workflowNodes.length === 0) return;

    const cols = Math.ceil(Math.sqrt(workflowNodes.length));
    const spacing = { x: 220, y: 100 };
    const start = { x: 60, y: 60 };

    // Sort: orchestrators first
    const sorted = [...workflowNodes].sort((a, b) => {
        if (a.type === 'orchestrator' && b.type !== 'orchestrator') return -1;
        if (a.type !== 'orchestrator' && b.type === 'orchestrator') return 1;
        return 0;
    });

    sorted.forEach((node, i) => {
        const col = i % cols;
        const row = Math.floor(i / cols);
        node.position = {
            x: start.x + col * spacing.x,
            y: start.y + row * spacing.y
        };
    });

    renderWorkflowCanvas();
}

