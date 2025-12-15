FROM python:3.13-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend app and any resources it may use
COPY webapp.py ./webapp.py
COPY prompts ./prompts

# Runtime configuration
ENV PORT=8001
EXPOSE 8001

# Start the Flask backend
CMD ["python", "webapp.py"]