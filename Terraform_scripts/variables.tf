variable "openai_key" {
  description = "OpenAI API Key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "gemini_key" {
  description = "Google Gemini API Key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "changi_api_key" {
  description = "Changi Airport API Key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "mcp_api_url" {
  description = "MCP API Gateway URL"
  type        = string
  default     = ""
}

variable "mcp_api_key" {
  description = "MCP API Gateway API Key"
  type        = string
  sensitive   = true
  default     = ""
}
