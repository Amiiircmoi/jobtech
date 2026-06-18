output "api_endpoint" {
  value = aws_api_gateway_stage.v1.invoke_url
}

output "rest_api_id" {
  value = aws_api_gateway_rest_api.api.id
}

output "kinesis_stream" {
  value = aws_kinesis_stream.fresh_jobs.name
}

output "lambda_name" {
  value = aws_lambda_function.indicator_api.function_name
}
