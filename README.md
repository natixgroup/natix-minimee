# 🧠 Minimee — Personal AI Agent System

Minimee est une application d'intelligence agentique personnelle qui apprend à connaître son utilisateur à travers ses conversations quotidiennes. Elle se connecte à WhatsApp et Gmail, analyse les échanges passés, construit une mémoire contextuelle active (via RAG et embeddings dans PostgreSQL/pgvector), et mobilise une équipe d'agents IA spécialisés capables de répondre ou d'agir à la place de l'utilisateur — toujours sous sa validation.

## 📁 Structure du Monorepo

```
minimee/
├── apps/
│   ├── dashboard/     # Next.js (App Router) - Dashboard SaaS
│   ├── backend/       # FastAPI - Orchestration IA
│   └── bridge/        # Node.js + Baileys - WhatsApp Bridge
├── packages/
│   └── shared/        # Types, prompts, utils partagés
├── infra/
│   ├── docker/        # Dockerfiles et docker-compose.yml
│   └── db/            # Migrations Alembic
├── scripts/           # Backup, restore, seed scripts
├── .env.example      # Variables d'environnement template
├── Makefile           # Commandes de développement
└── README.md          # Ce fichier
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
- Logs structurés et métriques

### Bridge - WhatsApp (Node.js + Baileys)
- Interface temps réel avec WhatsApp
- Auto-création groupe "Minimee TEAM"
- Réception et routage des messages

### Base de données (PostgreSQL + pgvector)
- Messages et conversations
- Embeddings vectoriels
- Agents, prompts, policies
- Paramètres utilisateur

## 🚀 Setup

### Prérequis
- Docker & Docker Compose
- Node.js 20+
- Python 3.11+
- PostgreSQL 16+ (avec pgvector extension)

### Installation

1. **Cloner le repository**
   ```bash
   git clone https://github.com/natixgroup/natix-minimee.git
   cd natix-minimee
   ```

2. **Configurer l'environnement**
   ```bash
   cp .env.example .env
   # Éditer .env avec vos configurations
   ```
   
   Variables importantes à configurer :
   - `DATABASE_URL` : URL de connexion PostgreSQL
   - `LLM_PROVIDER` : ollama, vllm, ou openai
   - `OPENAI_API_KEY` : Si vous utilisez OpenAI
   - `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` : Pour l'intégration Gmail

3. **Lancer les services**
   ```bash
   make up
   ```
   
   Ou manuellement :
   ```bash
   cd infra/docker && docker-compose up -d
   ```

4. **Initialiser la base de données**
   ```bash
   # Appliquer les migrations
   cd infra/db
   alembic upgrade head
   
   # Charger les données par défaut
   make seed
   # ou
   python3 scripts/seed_data.py
   ```

5. **Accéder aux services**
   - Dashboard: http://localhost:3002
   - API Backend: http://localhost:8001
   - API Docs: http://localhost:8001/docs
   - Health Check: http://localhost:8001/health
   - Metrics: http://localhost:8001/metrics

## 📋 Commandes Make

```bash
make help     # Affiche l'aide
make up       # Démarre tous les services
make down     # Arrête tous les services
make logs     # Affiche les logs
make build    # Build les images Docker
make restart  # Redémarre les services
make clean    # Nettoie volumes et containers
make test     # Lance les tests (backend + frontend)
make lint     # Lance le linting (backend + frontend)
make seed     # Charge les données par défaut
make backup   # Crée une sauvegarde de la base de données
make restore FILE=./backups/backup.sql.gz  # Restaure depuis un backup
```

## 🧩 Services Docker

- **postgres**: Base de données PostgreSQL avec pgvector (port 5432)
- **backend**: API FastAPI (port 8001 - externe, 8000 interne)
- **dashboard**: Next.js avec hot-reload (port 3000)
- **bridge**: Bridge WhatsApp Baileys
- **ollama**: LLM local (port 11434)

## 🔄 Workflow de Développement

1. **Hot-reload activé** : Les modifications dans `apps/` sont reflétées automatiquement
2. **Migrations DB** : Via Alembic dans `infra/db/`
3. **Types partagés** : Dans `packages/shared/`
4. **Logs structurés** : JSON logs avec request_id, métriques intégrées
5. **Tests** : `make test` ou `pytest tests/` pour le backend

## 🧪 Testing

### Backend Tests
```bash
cd apps/backend
pytest tests/ -v
```

### Frontend Tests
```bash
cd apps/dashboard
npm run type-check  # TypeScript validation
npm run lint        # ESLint
```

### Run All Tests
```bash
make test
```

## 📊 Monitoring & Métriques

- **Structured Logs** : JSON logs avec request_id, trace_id, métadonnées
- **Metrics Endpoint** : `GET /metrics` - Retourne latence (p50/p95/p99), RAG hits, LLM calls, erreurs
- **Request IDs** : Chaque requête a un ID unique dans les headers `X-Request-ID`
- **Latency Tracking** : Mesure automatique dans header `X-Process-Time`

## 💾 Backup & Restore

### Créer un backup
```bash
make backup
# ou
bash scripts/backup_db.sh
```

Les backups sont stockés dans `./backups/` avec timestamp.

### Restaurer un backup
```bash
make restore FILE=./backups/minimee_backup_20240101_120000.sql.gz
# ou
bash scripts/restore_db.sh ./backups/minimee_backup_20240101_120000.sql.gz
```

## 🚢 Deployment

### Production Considerations

1. **Environment Variables** : 
   - Utiliser un gestionnaire de secrets (AWS Secrets Manager, HashiCorp Vault, etc.)
   - Ne jamais commiter `.env` dans le repo

2. **Database** :
   - Utiliser PostgreSQL managé (AWS RDS, Google Cloud SQL, etc.)
   - Configurer backups automatiques
   - Monitoring et alertes

3. **SSL/TLS** :
   - Activer HTTPS pour toutes les communications
   - Mettre à jour `GMAIL_REDIRECT_URI` avec votre domaine

4. **Scaling** :
   - Backend : Utiliser un load balancer, multiple instances
   - Database : Read replicas pour les requêtes RAG
   - Queue system : Pour les tâches asynchrones (future enhancement)

5. **Monitoring** :
   - Intégrer Prometheus/Grafana pour les métriques
   - Centraliser les logs (ELK, Datadog, etc.)
   - Alertes sur erreurs et latence

## 📚 API Documentation

Une fois le backend démarré, accédez à :
- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc

## 🔐 Security

- OAuth 2.0 pour Gmail
- Tokens stockés de manière sécurisée
- Validation des entrées utilisateur
- Rate limiting (à implémenter pour production)

## 📝 Features Implemented

- ✅ Monorepo structure
- ✅ Docker orchestration
- ✅ Database schema with pgvector
- ✅ FastAPI backend with RAG
- ✅ Next.js dashboard
- ✅ WhatsApp bridge with Baileys
- ✅ Gmail OAuth and indexing
- ✅ Structured JSON logging
- ✅ Metrics tracking
- ✅ Comprehensive tests
- ✅ CI/CD pipeline
- ✅ Seed data scripts
- ✅ Backup/restore scripts

## 📄 Licence

Propriétaire - Tous droits réservés
