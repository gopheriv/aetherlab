FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AETHERLAB_LEADERBOARD_DB=/data/leaderboard.sqlite3

WORKDIR /app
COPY aetherlab /app/aetherlab
RUN useradd --system --uid 10001 physlab \
    && mkdir -p /data \
    && chown -R physlab:physlab /app /data

USER physlab
EXPOSE 8765
VOLUME ["/data"]
CMD ["python", "-m", "aetherlab.services.leaderboard_server", "--host", "0.0.0.0", "--port", "8765", "--db", "/data/leaderboard.sqlite3"]
