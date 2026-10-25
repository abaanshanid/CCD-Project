resource "aws_s3_bucket_cors_configuration" "original_images" {
  bucket = aws_s3_bucket.original_images.id

  cors_rule {
    allowed_headers = ["*"]

    allowed_methods = [
      "PUT",
      "HEAD"
    ]

    allowed_origins = [
      "http://localhost:3000",
      "http://localhost:5173",
      "https://ccd-project-ueyd.onrender.com"
    ]

    expose_headers = [
      "ETag"
    ]

    max_age_seconds = 3600
  }
}


resource "aws_s3_bucket_cors_configuration" "processed_images" {
  bucket = aws_s3_bucket.processed_images.id

  cors_rule {
    allowed_headers = ["*"]

    allowed_methods = [
      "GET",
      "HEAD"
    ]

    allowed_origins = [
      "http://localhost:3000",
      "http://localhost:5173",
      "https://ccd-project-ueyd.onrender.com"
    ]

    expose_headers = [
      "ETag"
    ]

    max_age_seconds = 3600
  }
}
