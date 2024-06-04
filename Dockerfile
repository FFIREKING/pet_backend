# Use Python slim image as base
FROM python:3.12-slim-bookworm

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8000 to the outside world
EXPOSE 8000

# Command to run the Flask application using Uvicorn server
CMD ["uvicorn", "app:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
