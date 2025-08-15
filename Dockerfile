FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install uv

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "bot.py"]