output "bucket_name" { value = aws_s3_bucket.this.bucket }
output "bucket_arn" { value = aws_s3_bucket.this.arn }
output "access_log_bucket_name" { value = aws_s3_bucket.access_logs.bucket }
