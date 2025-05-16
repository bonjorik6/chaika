# Используем официальный образ Python
FROM python:3.10-slim

# Рабочая директория
WORKDIR /app

# Скопируем requirements и установим зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Скопируем всю вашу логику
COPY . .

# По умолчанию запускаем именно server.py
CMD ["python", "server.py"]
