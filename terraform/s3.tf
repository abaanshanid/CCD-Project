resource "aws_s3_bucket" "original_images" {
  bucket = "${var.project_name}-originals-${random_id.bucket_suffix.hex}"

  # Lets Terraform delete this development bucket even if it contains images.
  force_destroy = true
}

resource "aws_s3_bucket" "processed_images" {
  bucket = "${var.project_name}-processed-${random_id.bucket_suffix.hex}"

  force_destroy = true
}


# Block public access

resource "aws_s3_bucket_public_access_block" "original_images" {
  bucket = aws_s3_bucket.original_images.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "processed_images" {
  bucket = aws_s3_bucket.processed_images.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}


# Server-side encryption

resource "aws_s3_bucket_server_side_encryption_configuration" "original_images" {
  bucket = aws_s3_bucket.original_images.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "processed_images" {
  bucket = aws_s3_bucket.processed_images.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}


# Automatically remove old project images to control storage costs

resource "aws_s3_bucket_lifecycle_configuration" "original_images" {
  bucket = aws_s3_bucket.original_images.id

  rule {
    id     = "delete-old-original-images"
    status = "Enabled"

    filter {}

    expiration {
      days = 7
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "processed_images" {
  bucket = aws_s3_bucket.processed_images.id

  rule {
    id     = "delete-old-processed-images"
    status = "Enabled"

    filter {}

    expiration {
      days = 7
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}