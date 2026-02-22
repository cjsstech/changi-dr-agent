provider "aws" {
  region = "ap-south-1"
}

terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

# 1️⃣ Use existing bucket
data "aws_s3_bucket" "artifact_bucket" {
  bucket = "agent-dr-artifacts"
}

# 2️⃣ Upload zip pre-built by deploy.ps1
resource "aws_s3_object" "lambda_upload" {
  bucket = data.aws_s3_bucket.artifact_bucket.id
  key    = "agent-dr.zip"
  source = "${path.module}/../agent-dr.zip"
  etag   = try(filemd5("${path.module}/../agent-dr.zip"), "")
}

# 4️⃣ Deploy SAM template
resource "aws_cloudformation_stack" "agent_stack" {

  depends_on = [aws_s3_object.lambda_upload]

  name          = "agent-cag-dr"
  template_body = file("${path.module}/../template.yaml")

  parameters = {
    AgentFunctionName = "agent-dr-chat"
    OpenAIKey         = var.openai_key
    GeminiKey         = var.gemini_key
    ChangiApiKey      = var.changi_api_key
    FileBucketName    = "agent-dr-artifacts"
    SessionTTL        = "3600"
    McpApiUrl         = var.mcp_api_url
  }

  capabilities = [
    "CAPABILITY_IAM",
    "CAPABILITY_NAMED_IAM",
    "CAPABILITY_AUTO_EXPAND"
  ]
}

output "api_url" {
  value = aws_cloudformation_stack.agent_stack.outputs["ApiUrl"]
}