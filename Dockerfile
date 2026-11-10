FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
# Retrieval runs on CPU. Ollama manages generation separately.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.6.0 \
    && pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.headless=true"]
