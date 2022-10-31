FROM python:3.9-alpine

LABEL Name=pvLimiter=0.0.1

WORKDIR /
COPY requirements.txt .

# pip Ausführen
RUN python3 -m pip install -r requirements.txt

COPY limiter.py /

# Skript beim start einmal ausführen und dach cron deamon starten
CMD python /limiter.py

