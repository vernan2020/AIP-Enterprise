FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY ticotrader_web/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY src /app/src
COPY ticotrader_web /app/ticotrader_web
RUN useradd --uid 10001 --create-home trader && mkdir -p /app/src/database /app/database && chown -R trader:trader /app
USER trader
ENV PYTHONPATH=/app/src:/app AIP_EXECUTION_MODE=CONFIGURED AIP_DEMO_MODE_ENABLED=false TICOTRADER_BIND=0.0.0.0
EXPOSE 8080
CMD ["python", "ticotrader_web/start.py"]
