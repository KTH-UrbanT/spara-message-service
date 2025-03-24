# Use an official Python image as the base image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /message-service

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the FastAPI application code
COPY . .

# Expose port 8000 for the FastAPI app
EXPOSE 8000

# Start the FastAPI server
CMD ["uvicorn", "main:socket_app", "--host", "0.0.0.0", "--port", "8000"]
