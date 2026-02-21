provider "aws" {
  region = "ap-south-1"
}

terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
    null = {
      source = "hashicorp/null"
    }
  }
}

# 1️⃣ Build Lambda zip (code + pip deps including jinja2) so Lambda can import
resource "null_resource" "build_lambda_zip" {
  triggers = {
    requirements = filemd5("${path.module}/../requirements.txt")
    script       = filemd5("${path.module}/../build_lambda.sh")
  }
  provisioner "local-exec" {
    command     = "chmod +x build_lambda.sh && ./build_lambda.sh"
    working_dir = "${path.module}/.."
  }
}

# 2️⃣ Use existing bucket
data "aws_s3_bucket" "artifact_bucket" {
  bucket = "agent-dr-artifacts"
}

# 3️⃣ Upload zip (produced by build_lambda.sh at repo root)
resource "aws_s3_object" "lambda_upload" {
  depends_on = [null_resource.build_lambda_zip]
  bucket     = data.aws_s3_bucket.artifact_bucket.id
  key        = "agent-dr.zip"
  source     = "${path.module}/../agent-dr.zip"
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
    McpApiKey         = var.mcp_api_key
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