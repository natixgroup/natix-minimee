# 🧠 Minimee — Personal AI Agent System

Minimee est une application d'intelligence agentique personnelle qui apprend à connaître son utilisateur à travers ses conversations quotidiennes. Elle se connecte à WhatsApp et Gmail, analyse les échanges passés, construit une mémoire contextuelle active (via RAG et embeddings dans PostgreSQL/pgvector), et mobilise une équipe d'agents IA spécialisés capables de répondre ou d'agir à la place de l'utilisateur — toujours sous sa validation.

## 📁 Structure du Monorepo

```
minimee/
├── apps/
│   ├── dashboard/     # Next.js (App Router) - Dashboard SaaS
│   ├── backend/        # FastAPI - Orchestration IA
│   └── bridge/         # Node.js + Baileys - WhatsApp Bridge
├── packages/
│   └── shared/         # Types, prompts, utils partagés
├── infra/
│   ├── docker/         # Dockerfiles et docker-compose.yml
│   └── db/             # Migrations Alembic
├── .env.example        # Variables d'environnement template
├── Makefile            # Commandes de développement
└── README.md           # Ce fichier
```

## 🏗️ Architecture

### Frontend - Dashboard (Next.js)
- Configuration des agents
- Sélection du LLM (Ollama/vLLM/OpenAI)
- Gestion des embeddings
- Import conversations WhatsApp
- OAuth Gmail

### Backend - API (FastAPI)
- Orchestration IA (RAG, LLM router)
- Embeddings Hugging Face
- Gestion des agents
- Service Gmail
- Logs et monitoring

### Bridge - WhatsApp (Node.js + Baileys)
- Interface temps réel avec WhatsApp
- Auto-création groupe "Minimee TEAM"
- Réception et routage des messages

### Base de données (PostgreSQL + pgvector)
- Messages et conversations
- Embeddings vectoriels
- Agents, prompts, policies
- Paramètres utilisateur

## 🚀 Démarrage Rapide

### Prérequis
- Docker & Docker Compose
- Node.js 20+
- Python 3.11+

### Installation

1. **Cloner et configurer l'environnement**
   ```bash
   cp .env.example .env
   # Éditer .env avec vos configurations
   ```

2. **Lancer les services**
   ```bash
   make up
   ```

3. **Accéder aux services**
   - Dashboard: http://localhost:3000
   - API Backend: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## 📋 Commandes Make

```bash
make help     # Affiche l'aide
make up       # Démarre tous les services
make down     # Arrête tous les services
make logs     # Affiche les logs
make build    # Build les images Docker
make restart  # Redémarre les services
make clean    # Nettoie volumes et containers
```

## 🧩 Services Docker

- **postgres**: Base de données PostgreSQL avec pgvector
- **backend**: API FastAPI (port 8000)
- **dashboard**: Next.js avec hot-reload (port 3000)
- **bridge**: Bridge WhatsApp Baileys
- **ollama**: LLM local (port 11434)

## 🔄 Workflow de Développement

1. Les services sont en mode développement avec hot-reload
2. Les modifications dans `apps/` sont reflétées automatiquement
3. Les migrations DB se font via Alembic dans `infra/db/`
4. Les types partagés sont dans `packages/shared/`

## 📝 Prochaines Étapes

- [ ] Configuration initiale de la base de données
- [ ] Implémentation RAG avec pgvector
- [ ] Intégration LLM providers
- [ ] Interface WhatsApp complète
- [ ] OAuth Gmail
- [ ] Dashboard de configuration des agents

## 📄 Licence

Propriétaire - Tous droits réservés

