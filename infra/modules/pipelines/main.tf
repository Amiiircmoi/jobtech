# ── Pipelines & service cloud : Kinesis (flux), Lambda (traitement/service), API GW ──
# Services cloud d'extraction/transformation, flux temps réel, IAM least-privilege,
# logs CloudWatch.

# ── Flux temps réel minimal (offres « fraîches ») ───────────────────────────
resource "aws_kinesis_stream" "fresh_jobs" {
  name             = "${var.project}-fresh-jobs-${var.name_suffix}"
  shard_count      = 1
  retention_period = 24
}

# ── Rôle d'exécution Lambda (least-privilege) ───────────────────────────────
resource "aws_iam_role" "lambda_exec" {
  name = "${var.project}-lambda-exec-${var.name_suffix}"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "lambda_exec" {
  role = aws_iam_role.lambda_exec.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:Query"]
        Resource = var.indicators_table_arn
      },
      {
        Effect   = "Allow"
        Action   = ["kinesis:GetRecords", "kinesis:GetShardIterator", "kinesis:DescribeStream", "kinesis:ListShards"]
        Resource = aws_kinesis_stream.fresh_jobs.arn
      },
    ]
  })
}

# ── Packaging + fonction Lambda ─────────────────────────────────────────────
data "archive_file" "indicator_api" {
  type        = "zip"
  source_dir  = "${path.module}/../../lambda/indicator_api"
  output_path = "${path.module}/../../lambda/indicator_api.zip"
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project}-indicator-api-${var.name_suffix}"
  retention_in_days = 14
}

resource "aws_lambda_function" "indicator_api" {
  function_name    = "${var.project}-indicator-api-${var.name_suffix}"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.handler"
  runtime          = "python3.11"
  filename         = data.archive_file.indicator_api.output_path
  source_code_hash = data.archive_file.indicator_api.output_base64sha256
  timeout          = 15
  environment {
    variables = { INDICATORS_TABLE = var.indicators_table_name }
  }
  depends_on = [aws_cloudwatch_log_group.lambda]
}

# ── API Gateway REST (v1) : expose GET /indicators ──────────────────────────
# v1 REST (et non v2 HTTP) : supportée par LocalStack Community ET le vrai AWS.
resource "aws_api_gateway_rest_api" "api" {
  name = "${var.project}-api-${var.name_suffix}"
}

resource "aws_api_gateway_resource" "indicators" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "indicators"
}

resource "aws_api_gateway_method" "get" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.indicators.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.indicators.id
  http_method             = aws_api_gateway_method.get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.indicator_api.invoke_arn
}

resource "aws_api_gateway_deployment" "this" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  depends_on  = [aws_api_gateway_integration.lambda]
  triggers    = { redeploy = sha1(jsonencode(aws_api_gateway_integration.lambda)) }
  lifecycle { create_before_destroy = true }
}

resource "aws_api_gateway_stage" "v1" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  deployment_id = aws_api_gateway_deployment.this.id
  stage_name    = "v1"
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.indicator_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}
