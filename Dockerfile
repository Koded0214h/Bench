# Bench — production image.
#
# The app runs from /app/src on PYTHONPATH rather than being pip-installed:
# settings.py derives BASE_DIR from its own location (four parents up = repo
# root), so importing bench from site-packages would put FRONTEND_DIST and the
# sqlite file somewhere inside the venv instead of the project.

FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    DJANGO_SETTINGS_MODULE=bench.control_plane.settings
WORKDIR /app

# Kept in step with pyproject.toml's dependencies, plus the WSGI server.
RUN pip install --no-cache-dir \
      "httpx>=0.27" \
      "solari-browser>=0.1.3" \
      "solari-sandbox>=0.2.0" \
      "solari-desktop>=0.2.0" \
      "PyYAML>=6.0" \
      "anthropic>=0.40" \
      "langgraph>=0.2" \
      "Django>=5.0" \
      "djangorestframework>=3.15" \
      "djangorestframework-simplejwt>=5.3" \
      "django-cors-headers>=4.4" \
      "gunicorn>=22.0"

COPY manage.py ./
COPY src/ ./src/
COPY --from=frontend /app/frontend/dist ./frontend/dist

RUN mkdir -p /app/.bench
EXPOSE 8000

# migrate is idempotent; collectstatic keeps the admin usable behind DEBUG=false.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && exec gunicorn bench.control_plane.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120 --access-logfile -"]
