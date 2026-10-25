output "aws_region" {
  value = var.aws_region
}

output "original_images_bucket" {
  value = aws_s3_bucket.original_images.bucket
}

output "processed_images_bucket" {
  value = aws_s3_bucket.processed_images.bucket
}

output "processing_queue_url" {
  value = aws_sqs_queue.image_processing.url
}

output "processing_queue_arn" {
  value = aws_sqs_queue.image_processing.arn
}

output "dead_letter_queue_url" {
  value = aws_sqs_queue.image_processing_dead_letter.url
}

output "batches_table_name" {
  value = aws_dynamodb_table.batches.name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.image_worker.repository_url
}

output "lambda_function_name" {
  value = aws_lambda_function.image_worker.function_name
}

output "lambda_log_group" {
  value = aws_cloudwatch_log_group.image_worker.name
}

output "api_url" {
  value = aws_apigatewayv2_api.cloud_api.api_endpoint
}

output "api_documentation_url" {
  value = "${aws_apigatewayv2_api.cloud_api.api_endpoint}/docs"
}