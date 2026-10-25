variable "aws_region" {
  description = "AWS region used for the project"
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Project name used when naming resources"
  type        = string
  default     = "ccd-image-processor"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}