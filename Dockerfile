FROM python:3.10-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget gnupg unzip curl fonts-liberation libappindicator3-1 libasound2 libatk-bridge2.0-0 \
    libatk1.0-0 libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 libnspr4 libnss3 \
    libxcomposite1 libxdamage1 libxrandr2 xdg-utils libu2f-udev \
    libvulkan1 libxss1 libnss3-dev chromium chromium-driver \
 && apt-get clean

# Set display port to avoid crash
ENV DISPLAY=:99

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . /app
WORKDIR /app

CMD ["python", "main.py"]
