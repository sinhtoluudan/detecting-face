FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources && apt-get update && apt-get install -y --no-install-recommends build-essential libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*
WORKDIR /repo/web/backend
COPY web/backend/requirements*.txt ./
ARG INSTALL_FACE=true
RUN if [ "$INSTALL_FACE" = "true" ]; then pip install --no-cache-dir -r requirements-face.txt; else pip install --no-cache-dir -r requirements.txt; fi
COPY core.py camera.py region_match.py regions.py config.json /repo/
COPY web/backend /repo/web/backend
COPY web/scripts /repo/web/scripts
EXPOSE 8000
# Compound business operations intentionally run in ONE process.
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--workers","1"]
