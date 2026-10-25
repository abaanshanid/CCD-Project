# Retrieves the digest of the container currently tagged "latest".

data "aws_ecr_image" "image_worker" {
  repository_name = aws_ecr_repository.image_worker.name
  image_tag       = "latest"
}


resource "aws_cloudwatch_log_group" "image_worker" {
  name = "/aws/lambda/${var.project_name}-worker-${var.environment}"

  retention_in_days = 7
}


resource "aws_lambda_function" "image_worker" {
  function_name = "${var.project_name}-worker-${var.environment}"

  role         = aws_iam_role.image_worker.arn
  package_type = "Image"

  # Use the immutable digest rather than only the latest tag.
  image_uri = "${aws_ecr_repository.image_worker.repository_url}@${data.aws_ecr_image.image_worker.image_digest}"

  architectures = ["x86_64"]

  memory_size = 3008
  timeout     = 180


  ephemeral_storage {
    size = 1024
  }

  environment {
    variables = {
      INPUT_BUCKET    = aws_s3_bucket.original_images.bucket
      OUTPUT_BUCKET   = aws_s3_bucket.processed_images.bucket
      TABLE_NAME      = aws_dynamodb_table.batches.name
      NUMBA_CACHE_DIR = "/tmp/numba-cache"
      XDG_CACHE_HOME  = "/tmp/.cache"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.worker_sqs,
    aws_iam_role_policy.image_worker,
    aws_cloudwatch_log_group.image_worker
  ]
}


resource "aws_lambda_event_source_mapping" "image_processing_queue" {
  event_source_arn = aws_sqs_queue.image_processing.arn
  function_name    = aws_lambda_function.image_worker.arn

  # One SQS message represents one image.
  batch_size = 1
  enabled    = true

  scaling_config {
    maximum_concurrency = 2
  }

  depends_on = [
    aws_iam_role_policy_attachment.worker_sqs
  ]
}