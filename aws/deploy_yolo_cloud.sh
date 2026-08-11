#!/bin/sh
set -eu

REGION="${AWS_REGION:-ap-southeast-1}"
PROFILE="${AWS_PROFILE:-nt2204-new}"
STACK="${STACK_NAME:-nt2204-edge-chain}"
REPOSITORY="${ECR_REPOSITORY:-${STACK}-yolov8}"
TAG="${IMAGE_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
ACCOUNT_ID="$(aws --profile "$PROFILE" sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE_URI="${REGISTRY}/${REPOSITORY}:${TAG}"

aws --profile "$PROFILE" --region "$REGION" ecr describe-repositories \
  --repository-names "$REPOSITORY" >/dev/null 2>&1 || \
aws --profile "$PROFILE" --region "$REGION" ecr create-repository \
  --repository-name "$REPOSITORY" \
  --image-scanning-configuration scanOnPush=true >/dev/null

aws --profile "$PROFILE" --region "$REGION" ecr get-login-password | \
  docker login --username AWS --password-stdin "$REGISTRY"

cp yolov8n.pt aws/lambda_detect_yolo/yolov8n.pt
docker build --platform linux/arm64 \
  --tag "$IMAGE_URI" \
  aws/lambda_detect_yolo
docker push "$IMAGE_URI"

aws --profile "$PROFILE" cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK" \
  --template-file aws/cloudformation/template.yaml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides ProjectName="$STACK" DetectImageUri="$IMAGE_URI" \
  --no-fail-on-empty-changeset

aws --profile "$PROFILE" cloudformation describe-stacks \
  --region "$REGION" --stack-name "$STACK" \
  --query 'Stacks[0].Outputs' --output table

echo "YOLOv8n image deployed: $IMAGE_URI"
