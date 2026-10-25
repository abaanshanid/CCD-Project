resource "aws_sqs_queue" "image_processing_dead_letter" {
  name = "${var.project_name}-dead-letter-${var.environment}"

  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "image_processing" {
  name = "${var.project_name}-queue-${var.environment}"

  # Must be longer than the future Lambda timeout.
  visibility_timeout_seconds = 1200

  # Keep unprocessed messages for one day.
  message_retention_seconds = 86400

  receive_wait_time_seconds = 10

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.image_processing_dead_letter.arn
    maxReceiveCount     = 3
  })
}