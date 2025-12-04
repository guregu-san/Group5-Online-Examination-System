FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
EXPOSE 5001
ENV FLASK_APP=run.py
ENV PYTHONUNBUFFERED=1

CMD ["python", "run.py"]
