FROM pytorch/pytorch:2.0.0-cuda11.7-cudnn8-runtime

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install requirements with pinned versions to ensure compatibility
COPY requirements.txt .

# Clean up pip cache and ensure we have compatible versions
RUN pip install --no-cache-dir --upgrade pip && \
    pip uninstall -y flask werkzeug && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir flask==2.0.1 werkzeug==2.0.1

# Copy application code
COPY . .

# Create temp directory
RUN mkdir -p /app/temp
RUN chmod 777 /app/temp

# Run the application
CMD ["python", "server.py"]