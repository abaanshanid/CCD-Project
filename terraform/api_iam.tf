resource "aws_iam_role" "cloud_api" {
  name = "${var.project_name}-api-role-${var.environment}"

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


resource "aws_iam_role_policy_attachment" "cloud_api_logs" {
  role = aws_iam_role.cloud_api.name

  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}


resource "aws_iam_role_policy" "cloud_api" {
  name = "${var.project_name}-api-policy-${var.environment}"
  role = aws_iam_role.cloud_api.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "UploadOriginalImages"
        Effect = "Allow"

        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]

        Resource = "${aws_s3_bucket.original_images.arn}/*"
      },
      {
        Sid    = "DownloadProcessedImages"
        Effect = "Allow"

        Action = [
          "s3:GetObject"
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
        Sid    = "UseBatchTable"
        Effect = "Allow"

        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:Query",
          "dynamodb:DescribeTable"
        ]

        Resource = aws_dynamodb_table.batches.arn
      },
      {
        Sid    = "QueueImageJobs"
        Effect = "Allow"

        Action = [
          "sqs:SendMessage"
        ]

        Resource = aws_sqs_queue.image_processing.arn
      }
    ]
  })
}