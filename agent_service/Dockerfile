FROM python:3.11-slim

WORKDIR /app

# System dependencies for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies install karein
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Agent service code copy karein (package structure maintain karte hue)
COPY app/ ./agent_service/app/
COPY start.sh .

# Windows CRLF line-endings fix aur executable permission
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

EXPOSE 7860

CMD ["./start.sh"]