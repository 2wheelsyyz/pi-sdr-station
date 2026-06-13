FROM python:3.12-slim
RUN pip install --no-cache-dir flask docker pyyaml
COPY app.py /app/app.py
WORKDIR /app
EXPOSE 8093
CMD ["python", "-u", "app.py"]
