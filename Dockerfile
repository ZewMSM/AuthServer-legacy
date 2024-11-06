FROM python:3.12-slim-bullseye

RUN apt-get update && apt-get install -y whois && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

WORKDIR /app

RUN pip install -r requirements.txt

COPY . /app
CMD ["python", "main.py"]