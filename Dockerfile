FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . /app

EXPOSE 9005

CMD ["python", "main.py"]