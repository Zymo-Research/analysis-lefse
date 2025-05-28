FROM biobakery/lefse:latest

USER root

# Install Python 3 and system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    openssh-client \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    python3 \
    python3-pip \
    python3-dev \
    python3-apt \
    ca-certificates \
    build-essential \
    libpq-dev \
    && apt-get clean \
    && update-ca-certificates

# Install a pip version compatible with Python 3.5 (do NOT use modern pip that requires f-strings)
RUN python3 -m pip install pip==20.3.4 && \
    python3 -m pip install --no-cache-dir \
        pandas \
        requests \
        pymongo \
        sshtunnel

# Create work directory
RUN mkdir -p /data
WORKDIR /data

# Copy scripts into container
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY lefse_preprocessing.py /app/lefse_preprocessing.py
COPY submit_results.py /app/submit_results.py
COPY global-bundle.pem /app/global-bundle.pem

# Ensure entrypoint script is executable
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
