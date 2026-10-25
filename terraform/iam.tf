resource "aws_iam_role" "image_worker" {
  name = "${var.project_name}-worker-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "lambda.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}


# Allows Lambda to read and delete SQS messages and write logs

resource "aws_iam_role_policy_attachment" "worker_sqs" {
  role = aws_iam_role.image_worker.name

  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaSQSQueueExecutionRole"
}


# Project-specific S3 and DynamoDB permissions

resource "aws_iam_role_policy" "image_worker" {
  name = "${var.project_name}-worker-policy-${var.environment}"
  role = aws_iam_role.image_worker.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "ReadOriginalImages"
        Effect = "Allow"

        Action = [
          "s3:GetObject"
        ]

        Resource = "${aws_s3_bucket.original_images.arn}/*"
      },
      {
        Sid    = "WriteProcessedImages"
        Effect = "Allow"

        Action = [
          "s3:PutObject",
          "s3:AbortMultipartUpload"
        ]

        Resource = "${aws_s3_bucket.processed_images.arn}/*"
      },
      {
        Sid    = "UseImageBuckets"
        Effect = "Allow"

        Action = [
          "s3:GetBucketLocation",
          "s3:ListBucket"
        ]

        Resource = [
          aws_s3_bucket.original_images.arn,
          aws_s3_bucket.processed_images.arn
        ]
      },
      {
        Sid    = "UpdateBatchRecords"
        Effect = "Allow"

        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DescribeTable"
        ]

        Resource = aws_dynamodb_table.batches.arn
      }
    ]
  })
}