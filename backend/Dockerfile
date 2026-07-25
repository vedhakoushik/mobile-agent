FROM python:3.11-slim

WORKDIR /app

# system deps for lxml + Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 libxslt1.1 libpng16-16 libjpeg62-turbo \
    android-tools-adb \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# create kb_data directory
RUN mkdir -p /app/kb_data /app/assets

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
