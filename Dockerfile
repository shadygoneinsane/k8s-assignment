# Start from a small official Python image (Debian-based, slim = lightweight)
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Copy ONLY requirements first (smart caching: if code changes but deps
# don't, Docker reuses the installed-deps layer and rebuilds faster)
COPY app/requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the application code
COPY app/ .

# Document that the app listens on port 8000
EXPOSE 8000

# The command that runs when the container starts:
# launch uvicorn, serving our FastAPI "app" object from main.py,
# listening on all interfaces (0.0.0.0) so it's reachable from outside the pod
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]