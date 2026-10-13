FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 RUFF_CACHE_DIR=/app/var/ruff-cache
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --require-hashes -r requirements.txt \
    && useradd --create-home --uid 10001 app
COPY --chown=app:app . /app
RUN python scripts/fetch_geographic_data.py \
    && DJANGO_DEBUG=true python manage.py collectstatic --noinput \
    && mkdir -p /app/var /app/data/geographic \
    && chown -R app:app /app/var /app/data/geographic
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/v1/health/', timeout=3)"
ENTRYPOINT ["sh", "/app/scripts/docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--config", "config/gunicorn.py"]
