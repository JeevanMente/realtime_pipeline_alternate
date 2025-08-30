variable "aws_region" {
  type        = string
  description = "AWS region (e.g. us-east-1)"
  default     = "us-east-1"
}

variable "project" {
  type        = string
  default     = "ecom-rt"
  description = "Project prefix for names and tags"
}

variable "env" {
  type        = string
  default     = "dev"
  description = "Deployment environment"
}

variable "alert_email" {
  type        = string
  description = "Email for business alerts (SNS)"
}

variable "alarm_email" {
  type        = string
  description = "Email for CloudWatch alarms (SNS)"
}

variable "large_order_amount" {
  type        = number
  default     = 1500
  description = "Amount threshold to publish a business alert"
}

variable "lambda_memory_mb" {
  type        = number
  default     = 256
}

variable "lambda_timeout_s" {
  type        = number
  default     = 30
}

variable "dashboard_enabled" {
  type        = bool
  default     = true
  description = "Create CloudWatch dashboard"
}

variable "invalid_email"{ 
    type = string
    default = null 
}

# Logging level for the Lambda function
variable "log_level" {
  type        = string
  description = "Lambda log level"
  default     = "INFO"
  validation {
    condition     = contains(["DEBUG","INFO","WARNING","ERROR","CRITICAL"], upper(var.log_level))
    error_message = "log_level must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL."
  }
}
