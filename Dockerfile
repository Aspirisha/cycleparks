# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your bot code
# COPY main.py .
# COPY cycleparks/ .

# Set environment variables for Python
ENV PYTHONUNBUFFERED=1

# Command to run your bot
CMD ["python", "main.py"]
