FROM nvcr.io/nvidia/deepstream:8.0-samples-multiarch

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY . .

ENTRYPOINT ["python3", "/app/main.py"]