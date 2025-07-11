# LEfSe Lambda Analysis

## Setup

### Prerequisites
1. Install pre-commit for code quality checks:
   ```bash
   pip install pre-commit
   pre-commit install
   ```

### Build and Deploy

1. **Build Docker image locally:**
   ```bash
   docker build -t lefse-lambda .
   ```

2. **Login to AWS ECR:**
   ```bash
   aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin 256056681342.dkr.ecr.ap-southeast-1.amazonaws.com
   ```

3. **Build and push to ECR:**
   ```bash
   docker buildx build \
     --platform linux/amd64 \
     --provenance=false \
     --push \
     -t 256056681342.dkr.ecr.ap-southeast-1.amazonaws.com/iomics/analyses/lefse-lambda:latest \
     .
   ```

4. **Update Lambda function:**
   ENV options include: dev, staging, prod
   ```bash
   aws lambda update-function-configuration \
      --function-name lefseAnalysisLambda \
      --region ap-southeast-1 \
      --environment Variables="{ENV=dev,API_KEY=/dev/data_access/API_KEY,PORTAL_API_URL=https://test-data-access.iomics.io}"
   ```

## Local Testing

1. **Build local test image:**
   ```bash
   docker build -t lambda-built-manual-local .
   ```

2. **Run locally:**
   ```bash
   docker run -p 9000:8080 lambda-built-manual-local
   ```

3. **Test with sample request:**
   ```bash
   curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
     -d '{
       "workspace_id": "402eae8f-55ad-427b-9724-bf569c11a4a2",
       "analysis_id": "63f9546d-f467-41ed-a9ba-
