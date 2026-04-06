FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Install Playwright browsers for JS-heavy sites
RUN pip install playwright && playwright install chromium --with-deps

COPY . .

CMD ["scrapy", "list"]
