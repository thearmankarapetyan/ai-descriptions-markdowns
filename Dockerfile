FROM python:3.10
WORKDIR /app2
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
