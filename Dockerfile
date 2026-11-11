FROM nvcr.io/nvidia/deepstream:8.0-samples-multiarch

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY . .

ENTRYPOINT ["python3", "/app/main.py"]