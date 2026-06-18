output "bucket_name" {
  value = aws_s3_bucket.lake.id
}

output "kms_key_arn" {
  value = aws_kms_key.lake.arn
}
