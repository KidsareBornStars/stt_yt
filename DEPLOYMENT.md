# Cloud Deployment Instructions

## Prerequisites
- Docker installed locally for building containers
- Cloud provider accounts (AWS/GCP) with appropriate permissions
- Cloud provider CLI tools installed

## GCP Deployment Options

### Option 1: Google App Engine

1. **Setup and Installation**
   ```bash
   # Install Google Cloud SDK if needed
   # https://cloud.google.com/sdk/docs/install
   
   # Login to Google Cloud
   gcloud auth login
   
   # Set your project ID
   gcloud config set project YOUR_PROJECT_ID
   ```

2. **Update Environment Variables**
   - Edit `app.yaml` and set your actual YouTube API key

3. **Deploy the Application**
   ```bash
   gcloud app deploy
   ```

4. **Access the Application**
   ```bash
   gcloud app browse
   ```

### Option 2: Google Cloud Run

1. **Setup and Installation**
   ```bash
   # Login to Google Cloud
   gcloud auth login
   
   # Set your project ID
   gcloud config set project YOUR_PROJECT_ID
   
   # Configure Docker to use Google Container Registry
   gcloud auth configure-docker
   ```

2. **Build and Deploy with Cloud Build**
   ```bash
   # Set your YouTube API key as a substitution variable
   gcloud builds submit --substitutions=_YOUTUBE_API_KEY=YOUR_API_KEY
   ```

3. **Alternative: Manual Deployment**
   ```bash
   # Build your Docker image
   docker build -t gcr.io/YOUR_PROJECT_ID/stt-yt-app .
   
   # Push image to Google Container Registry
   docker push gcr.io/YOUR_PROJECT_ID/stt-yt-app
   
   # Deploy to Cloud Run
   gcloud run deploy stt-yt-app \
     --image gcr.io/YOUR_PROJECT_ID/stt-yt-app \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --memory 2Gi \
     --set-env-vars=YOUTUBE_API_KEY=YOUR_API_KEY,FLASK_ENV=production
   ```

## AWS Deployment Options

### Option 1: AWS Elastic Beanstalk

1. **Setup and Installation**
   ```bash
   # Install AWS CLI and EB CLI
   pip install awscli awsebcli
   
   # Configure AWS CLI
   aws configure
   ```

2. **Update Environment Variables**
   - Edit `.ebextensions/01_flask.config` and set your actual YouTube API key

3. **Initialize EB Application**
   ```bash
   # Initialize EB application
   eb init -p python-3.9 stt-yt-app --region us-west-2
   ```

4. **Create an Environment and Deploy**
   ```bash
   eb create stt-yt-production
   ```

5. **Access the Application**
   ```bash
   eb open
   ```

### Option 2: AWS ECS with Fargate

1. **Create ECR Repository**
   ```bash
   aws ecr create-repository --repository-name stt-yt-app
   ```

2. **Build and Push Docker Image**
   ```bash
   # Log in to ECR
   aws ecr get-login-password | docker login --username AWS --password-stdin YOUR_AWS_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com
   
   # Build image
   docker build -t YOUR_AWS_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/stt-yt-app:latest .
   
   # Push image
   docker push YOUR_AWS_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/stt-yt-app:latest
   ```

3. **Deploy using AWS ECS Console**
   - Create a task definition with appropriate memory (min 2GB) and CPU allocations
   - Configure environment variables in the task definition
   - Create a Fargate service using the task definition

## Important Notes

1. **GPU Support**
   - The application currently checks for CUDA availability, but standard cloud instances won't have GPUs by default
   - For GCP: Use a GPU-enabled instance type if needed
   - For AWS: Use an accelerated computing instance type (g4dn, p3, etc.)

2. **Scaling and Cost Considerations**
   - Configure auto-scaling based on your traffic patterns
   - Monitor resource usage as speech-to-text processing can be resource-intensive

3. **Security**
   - Never commit API keys directly to code
   - Use environment variables or secret management services (GCP Secret Manager, AWS Secrets Manager)
   
4. **Storage**
   - The current implementation uses temporary local storage
   - Consider using cloud storage (GCS, S3) for more permanent storage solutions