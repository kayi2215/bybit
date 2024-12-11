FROM python:3.12-slim

WORKDIR /app

# Installation des dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copie des fichiers de dépendances
COPY requirements.txt .

# Installation des dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source
COPY src/ ./src/
COPY main.py .

# Création des répertoires nécessaires
RUN mkdir -p logs config

CMD ["python", "main.py"]
