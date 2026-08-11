#!/bin/sh
set -eu
REGION="${AWS_REGION:-ap-southeast-1}"
STACK="${STACK_NAME:-nt2204-edge-chain}"
BUCKET="$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue|[0]" --output text)"
aws s3 rm "s3://$BUCKET" --recursive --region "$REGION"
aws cloudformation delete-stack --region "$REGION" --stack-name "$STACK"
aws cloudformation wait stack-delete-complete --region "$REGION" --stack-name "$STACK"

