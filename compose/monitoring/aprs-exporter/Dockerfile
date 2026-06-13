FROM python:3.12-slim
RUN pip install --no-cache-dir prometheus_client
COPY exporter.py /app/exporter.py
WORKDIR /app
EXPOSE 9101
CMD ["python", "-u", "exporter.py"]
