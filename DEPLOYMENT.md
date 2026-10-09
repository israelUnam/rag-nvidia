# Cloud Run Deployment Guide

## 🚨 Quick Fix for Current Deployment Failure

The deployment failed because Cloud Run needs environment variables. Here's how to fix it:

### 1. Set Environment Variables in Cloud Run

Go to your Cloud Run service and set these environment variables:

```bash
# Required Supabase Configuration
SUPABASE_URL=your_supabase_url_here
SUPABASE_ANON_KEY=your_supabase_anon_key_here  
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_here

# Required NVIDIA API Catalog Configuration (https://build.nvidia.com)
NVIDIA_API_KEY=your_nvidia_api_key_here
NVIDIA_MODEL=google/gemma-4-31b-it
NVIDIA_EMBED_MODEL=nvidia/nemotron-3-embed-1b
EMBEDDING_DIMENSIONS=2048

# Application Configuration
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### 2. Deploy with Environment Variables via CLI

```bash
gcloud run deploy rag-openrouter \
  --source . \
  --platform managed \
  --region us-east1 \
  --allow-unauthenticated \
  --set-env-vars="SUPABASE_URL=your_url,SUPABASE_ANON_KEY=your_key,SUPABASE_SERVICE_ROLE_KEY=your_service_key,NVIDIA_API_KEY=your_nvidia_key,NVIDIA_MODEL=google/gemma-4-31b-it,NVIDIA_EMBED_MODEL=nvidia/nemotron-3-embed-1b,EMBEDDING_DIMENSIONS=2048,ENVIRONMENT=production,LOG_LEVEL=INFO" \
  --timeout=300 \
  --memory=1Gi \
  --cpu=1 \
  --max-instances=10 \
  --port=8080
```

### 3. Alternative: Use Cloud Console

1. Go to [Cloud Run Console](https://console.cloud.google.com/run)
2. Click on your `rag-openrouter` service
3. Click "Edit & Deploy New Revision"
4. Go to "Variables & Secrets" tab
5. Add the environment variables listed above
6. Click "Deploy"

## 🔧 What Was Fixed

1. **Dockerfile improvements:**
   - Added non-root user for security
   - Use `${PORT:-8080}` to respect Cloud Run's PORT variable
   - Added `--timeout-keep-alive 0` for better Cloud Run compatibility

2. **Environment variable handling:**
   - App now requires proper environment variables to start
   - Clear error messages if variables are missing

## 🚀 Testing the Deployment

Once deployed, test these endpoints:

```bash
# Health check
curl https://your-service-url/healthz

# Chat interface
curl https://your-service-url/chat

# Seed documents
curl -X POST https://your-service-url/seed

# Ask question
curl -X POST https://your-service-url/answer \
  -H "Content-Type: application/json" \
  -d '{"query": "Can I return shoes?"}'
```

## 📝 Notes

- **Memory**: Set to at least 1GB for AI operations
- **Timeout**: Set to 300s for embedding operations
- **CPU**: 1 CPU should be sufficient for moderate load
- **Concurrency**: Default (80) should work well

## 🔐 Security

- All environment variables should be set as secrets in production
- Consider using Google Secret Manager for sensitive data
- Enable authentication if needed for production use
