resource "aws_cloudwatch_log_group" "cloud_api" {
  name = "/aws/lambda/${var.project_name}-api-${var.environment}"

  retention_in_days = 7
}


resource "aws_lambda_function" "cloud_api" {
  function_name = "${var.project_name}-api-${var.environment}"

  role         = aws_iam_role.cloud_api.arn
  package_type = "Image"

  image_uri = "${aws_ecr_repository.image_worker.repository_url}@${data.aws_ecr_image.image_worker.image_digest}"

  architectures = ["x86_64"]

  memory_size = 512
  timeout     = 30

  image_config {
    command = ["cloud_api.handler"]
  }

  environment {
    variables = {
      INPUT_BUCKET  = aws_s3_bucket.original_images.bucket
      OUTPUT_BUCKET = aws_s3_bucket.processed_images.bucket
      TABLE_NAME    = aws_dynamodb_table.batches.name
      QUEUE_URL     = aws_sqs_queue.image_processing.url
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.cloud_api_logs,
    aws_iam_role_policy.cloud_api,
    aws_cloudwatch_log_group.cloud_api
  ]
}


resource "aws_apigatewayv2_api" "cloud_api" {
  name          = "${var.project_name}-api-${var.environment}"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = [
      "http://localhost:3000",
      "http://localhost:5173"
    ]

    allow_methods = [
      "GET",
      "POST",
      "OPTIONS"
    ]

    allow_headers = [
      "content-type"
    ]

    max_age = 3600
  }
}


resource "aws_apigatewayv2_integration" "cloud_api" {
  api_id = aws_apigatewayv2_api.cloud_api.id

  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.cloud_api.invoke_arn

  integration_method     = "POST"
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000
}


resource "aws_apigatewayv2_route" "cloud_api" {
  api_id = aws_apigatewayv2_api.cloud_api.id

  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.cloud_api.id}"
}


resource "aws_apigatewayv2_stage" "cloud_api" {
  api_id = aws_apigatewayv2_api.cloud_api.id

  name        = "$default"
  auto_deploy = true
}


resource "aws_lambda_permission" "allow_api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cloud_api.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_apigatewayv2_api.cloud_api.execution_arn}/*/*"
}