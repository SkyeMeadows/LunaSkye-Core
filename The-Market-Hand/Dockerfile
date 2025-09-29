# syntax=docker/dockerfile:1
FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
	cron \
	&& rm -rf /var/lib/apt/lists/*

WORKDIR /programs

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "MarketHand.py"]