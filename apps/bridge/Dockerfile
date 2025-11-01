FROM node:20-slim

# Installer git et autres dépendances nécessaires
RUN apt-get update && apt-get install -y git ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier les fichiers package
COPY package.json package-lock.json* ./

# Installer les dépendances
RUN npm ci || npm install

COPY . .

CMD ["npm", "start"]

