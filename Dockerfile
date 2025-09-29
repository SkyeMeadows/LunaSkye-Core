# syntax=docker/dockerfile:1
FROM ubuntu:latest

# Setup/check/update system
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /home/skye/programs

# Copy all files
COPY ./ ./

# Setup venv
RUN python3 -m venv .venv

# Install dependencies
RUN ./.venv/bin/pip install --upgrade pip && \
    ./.venv/bin/pip install -r requirements.txt

# Start the main program
CMD ["sh", "-c", "/home/skye/programs/.venv/bin/python db_setup.py ; /home/skye/programs/.venv/bin/python scheduler.py"]
