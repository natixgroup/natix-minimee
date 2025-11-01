FROM node:20-slim

# Installer git et autres dépendances nécessaires
RUN apt-get update && apt-get install -y git ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier les fichiers package
COPY package.json package-lock.json* ./

# Installer les dépendances (clean install pour éviter les problèmes de cache)
RUN npm ci --legacy-peer-deps || npm install --legacy-peer-deps

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]

