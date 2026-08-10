FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e ".[dev]"
EXPOSE 8000
CMD ["python3", "-m", "racedna", "serve", "--host", "0.0.0.0", "--port", "8000"]
