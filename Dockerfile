FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY lebdata/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY lebdata/ ./lebdata/
COPY workspace/ ./workspace/

# Expose port 5000
EXPOSE 5000

# Run the application
CMD ["python", "lebdata/lebdata/app.py"]
