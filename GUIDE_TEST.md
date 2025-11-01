# Guide de Test Complet - Minimee

Guide étape par étape pour tester toutes les fonctionnalités de Minimee avant la démo.

## 🚀 Étape 1 : Démarrage des Services

### 1.1 Vérifier les prérequis
```bash
# Vérifier Docker
docker --version
docker-compose --version

# Vérifier les ports disponibles
lsof -i :3000  # Dashboard
lsof -i :8001  # Backend (Minimee utilise 8001 pour éviter conflit avec lovaconnect sur 8000)
lsof -i :5432  # PostgreSQL
```

### 1.2 Configurer l'environnement
```bash
cd /Users/tarikzouine/git/minimee

# Copier et éditer .env si nécessaire
cp .env.example .env
# Éditer .env avec vos valeurs (OLLAMA_BASE_URL, etc.)
```

### 1.3 Démarrer tous les services
```bash
# Démarrer tous les conteneurs
make up

# OU manuellement
cd infra/docker && docker-compose up -d
```

### 1.4 Vérifier que tous les conteneurs sont en cours d'exécution
```bash
# Vérifier le statut des conteneurs
docker ps --filter "name=minimee" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Attendu : 5 conteneurs
# - minimee-postgres (healthy)
# - minimee-backend (running)
# - minimee-dashboard (running)
# - minimee-bridge (running)
# - ollama (running, optionnel)
```

**⏱️ Attendre 30-60 secondes** pour que tous les services démarrent.

---

## ✅ Étape 2 : Test Backend Health

### 2.1 Test Health Endpoint
```bash
# Test simple
curl http://localhost:8001/health

# Réponse attendue :
# {"status":"ok"}
```

### 2.2 Test avec détails
```bash
# Test avec headers
curl -v http://localhost:8001/health

# Vérifier les headers de réponse :
# - X-Process-Time (latence)
# - X-Request-ID (ID unique de requête)
```

### 2.3 Test Root Endpoint
```bash
curl http://localhost:8001/

# Réponse attendue :
# {"message":"Minimee API","status":"running","version":"0.1.0"}
```

**✅ Si vous obtenez `{"status":"ok"}`, le backend fonctionne !**

---

## 🌐 Étape 3 : Test Dashboard

### 3.1 Accéder au Dashboard
```bash
# Ouvrir dans le navigateur
open http://localhost:3002

# OU vérifier avec curl
curl -I http://localhost:3002
# Attendu : HTTP/1.1 200 OK
```

### 3.2 Vérifier les pages principales
1. **Overview** : http://localhost:3002/
   - Vérifier que les cartes statistiques s'affichent
   
2. **Minimee** : http://localhost:3002/minimee
   - Page principale pour tester l'approbation A/B/C
   
3. **Agents** : http://localhost:3002/agents
   - Liste des agents
   
4. **Logs** : http://localhost:3002/logs
   - Tableau des logs système
   
5. **Settings** : http://localhost:3002/settings
   - Configuration LLM, Embeddings, Gmail, etc.

**✅ Si toutes les pages se chargent, le dashboard fonctionne !**

---

## 📊 Étape 4 : Test RAG (Retrieval-Augmented Generation)

### 4.1 Préparer les données (si pas déjà fait)
```bash
# Option 1 : Seed la base de données avec des données par défaut
make seed

# Option 2 : Uploader un fichier WhatsApp via le dashboard
# - Aller sur Settings > WhatsApp tab
# - Uploader un fichier .txt WhatsApp
```

### 4.2 Test RAG via API
```bash
# Envoyer un message test qui devrait trouver des correspondances
curl -X POST http://localhost:8001/minimee/message \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Bonjour, comment ça va ?",
    "sender": "User",
    "timestamp": "2024-01-01T10:00:00Z",
    "conversation_id": "test_conv_001",
    "user_id": 1,
    "source": "dashboard"
  }'

# Réponse attendue :
# {
#   "message_id": 123,
#   "conversation_id": "test_conv_001",
#   "options": [
#     "Réponse A...",
#     "Réponse B...",
#     "Réponse C..."
#   ]
# }
```

### 4.3 Vérifier les métriques RAG
```bash
# Vérifier les métriques (RAG hits)
curl http://localhost:8001/metrics?window_minutes=60

# Vérifier dans la réponse :
# "rag": {
#   "hits": <nombre>,
#   "avg_similarity": <score>
# }
```

**✅ Si vous obtenez 3 options de réponse, le RAG fonctionne !**

---

## 💬 Étape 5 : Test A/B/C Approval UI

### 5.1 Test via Dashboard
1. **Accéder à la page Minimee**
   - Ouvrir http://localhost:3002/minimee

2. **Envoyer un message**
   - Taper un message dans le champ texte (ex: "Hello, how are you?")
   - Cliquer sur "Process Message"

3. **Vérifier le Dialog d'Approval**
   - Un dialog s'ouvre avec 3 options (A, B, C)
   - Chaque option affiche une réponse différente
   - Cliquer sur une option pour la sélectionner (bordure bleue)

4. **Approuver une option**
   - Sélectionner l'option A (ou B/C)
   - Cliquer sur "Approve Option A"
   - Vérifier la notification toast "Response approved and sent!"

5. **Tester Reject**
   - Envoyer un nouveau message
   - Cliquer sur "Reject All"
   - Vérifier la notification "Response rejected"

### 5.2 Test via API (alternative)
```bash
# 1. Traiter un message
RESPONSE=$(curl -s -X POST http://localhost:8000/minimee/message \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Test message",
    "sender": "User",
    "timestamp": "2024-01-01T10:00:00Z",
    "user_id": 1,
    "source": "dashboard"
  }')

# Extraire message_id (nécessite jq ou parsing manuel)
MESSAGE_ID=$(echo $RESPONSE | grep -o '"message_id":[0-9]*' | cut -d: -f2)

# 2. Approuver l'option A (index 0)
curl -X POST http://localhost:8001/minimee/approve \
  -H "Content-Type: application/json" \
  -d "{
    \"message_id\": $MESSAGE_ID,
    \"option_index\": 0,
    \"action\": \"yes\",
    \"type\": \"whatsapp_message\"
  }"

# Réponse attendue :
# {"status":"approved","message":"Response sent","sent":true}
```

**✅ Si le dialog s'affiche et l'approbation fonctionne, l'UI A/B/C fonctionne !**

---

## 📱 Étape 6 : Test WhatsApp Bridge

### 6.1 Vérifier les logs du bridge
```bash
# Voir les logs en temps réel
docker logs -f minimee-bridge

# OU les dernières lignes
docker logs --tail 50 minimee-bridge
```

### 6.2 Vérifier la connexion WhatsApp
Dans les logs, chercher :
```
✓ WhatsApp connected successfully
Minimee TEAM group ready: <group_id>
```

### 6.3 Si pas connecté (QR Code)
Si vous voyez :
```
QR Code generated - scan with WhatsApp
```
1. Scanner le QR code avec WhatsApp mobile
2. Attendre "✓ WhatsApp connected successfully"

### 6.4 Test envoi de message
1. **Envoyer un message au numéro connecté**
   - Depuis votre téléphone, envoyez "Hello Minimee" au numéro WhatsApp du bridge

2. **Vérifier les logs**
   ```bash
   docker logs --tail 20 minimee-bridge
   ```
   - Chercher : `[Message incoming]` avec votre message
   - Chercher : `Message processed by backend`

3. **Vérifier le backend**
   ```bash
   # Vérifier les logs backend
   docker logs --tail 20 minimee-backend
   ```
   - Chercher : `Processed message <id>, generated <n> options`

**✅ Si les messages sont reçus et traités, le bridge fonctionne !**

---

## 📧 Étape 7 : Test Gmail Connection & Sync

### 7.1 Préparer OAuth Gmail
**⚠️ Nécessite des credentials Gmail OAuth**

1. **Configurer .env**
   ```bash
   GMAIL_CLIENT_ID=your_client_id
   GMAIL_CLIENT_SECRET=your_client_secret
   GMAIL_REDIRECT_URI=http://localhost:8001/auth/gmail/callback
   ```

2. **Redémarrer le backend**
   ```bash
   docker restart minimee-backend
   ```

### 7.2 Connecter Gmail via Dashboard
1. **Ouvrir Settings > Gmail**
   - Aller sur http://localhost:3002/settings
   - Cliquer sur l'onglet "Gmail"

2. **Cliquer sur "Connect Gmail"**
   - Redirection vers Google OAuth
   - Autoriser l'accès
   - Redirection vers `/auth/gmail/callback`

3. **Vérifier le statut**
   - Le badge devrait afficher "Connected"
   - Un bouton "Fetch Recent Emails (30 days)" apparaît

### 7.3 Tester la récupération des emails
1. **Cliquer sur "Fetch Recent Emails (30 days)"**
   - Un toast "Gmail threads fetched and indexed successfully" apparaît

2. **Vérifier via API**
   ```bash
   # Vérifier le statut
   curl http://localhost:8001/gmail/status?user_id=1
   
   # Réponse attendue :
   # {"connected":true,"has_token":true}
   
   # Fetch threads
   curl "http://localhost:8001/gmail/fetch?days=30&only_replied=true&user_id=1"
   ```

3. **Vérifier l'indexation dans la DB**
   ```bash
   # Vérifier les messages Gmail dans la DB
   docker exec minimee-postgres psql -U minimee -d minimee \
     -c "SELECT COUNT(*) FROM messages WHERE source='gmail';"
   ```

**✅ Si Gmail est connecté et les threads sont indexés, Gmail fonctionne !**

---

## 🤖 Étape 8 : Test Agents CRUD

### 8.1 Créer un Agent
1. **Aller sur Agents** : http://localhost:3002/agents
2. **Cliquer sur "Create Agent"**
3. **Remplir le formulaire** :
   - Name: "Test Agent"
   - Role: "Customer Support"
   - Prompt: "You are a helpful customer support agent"
   - Style: "Professional and friendly"
   - Enabled: ✓
4. **Cliquer sur "Create Agent"**
5. **Vérifier** : L'agent apparaît dans la liste

### 8.2 Modifier un Agent
1. **Cliquer sur un agent dans la liste**
2. **Modifier les champs** (ex: changer le style)
3. **Cliquer sur "Update Agent"**
4. **Vérifier** : Les changements sont sauvegardés

### 8.3 Test via API
```bash
# Créer un agent
curl -X POST http://localhost:8001/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "API Test Agent",
    "role": "Test",
    "prompt": "Test prompt",
    "enabled": true,
    "user_id": 1
  }'

# Lister les agents
curl http://localhost:8001/agents?user_id=1

# Modifier un agent (remplacer <id> par l'ID réel)
curl -X PUT http://localhost:8001/agents/<id> \
  -H "Content-Type: application/json" \
  -d '{"style": "Updated style"}'
```

**✅ Si vous pouvez créer/modifier des agents, le CRUD fonctionne !**

---

## 🔄 Étape 9 : Test End-to-End Complet

### 9.1 Scénario complet : Message → RAG → Approval → Envoi
1. **Uploader des données WhatsApp** (si pas déjà fait)
   - Settings > WhatsApp > Uploader un fichier .txt

2. **Envoyer un message via Dashboard**
   - Aller sur http://localhost:3002/minimee
   - Taper un message similaire au contenu WhatsApp uploadé
   - Cliquer "Process Message"

3. **Vérifier les options générées**
   - 3 options A/B/C s'affichent
   - Les réponses doivent être contextuelles (utiliser RAG)

4. **Approuver une option**
   - Sélectionner l'option B
   - Cliquer "Approve Option B"
   - Vérifier la notification de succès

5. **Vérifier dans les logs**
   ```bash
   # Logs backend
   docker logs --tail 30 minimee-backend | grep -i "approved"
   
   # Logs metrics
   curl http://localhost:8001/metrics | jq '.rag'
   ```

### 9.2 Test avec WhatsApp réel
1. **Envoyer un message WhatsApp au bridge**
   - Depuis votre téléphone : "Bonjour, qu'est-ce que tu fais ?"

2. **Vérifier le traitement**
   ```bash
   docker logs --tail 50 minimee-bridge | grep -i "incoming"
   docker logs --tail 50 minimee-backend | grep -i "processed"
   ```

3. **Répondre via le bridge** (si implémenté)
   - Le bridge devrait envoyer la réponse approuvée

**✅ Si tout le flux fonctionne, le système est prêt pour la démo !**

---

## 📋 Checklist Rapide de Vérification

Exécutez ces commandes dans l'ordre :

```bash
# 1. Vérifier conteneurs
docker ps --filter "name=minimee" | wc -l
# Attendu : 5 (ou 4 si ollama pas démarré)

# 2. Test backend health
curl -s http://localhost:8001/health | grep -q "ok" && echo "✓ Backend OK" || echo "✗ Backend KO"

# 3. Test dashboard
curl -s -o /dev/null -w "%{http_code}" http://localhost:3002 | grep -q "200" && echo "✓ Dashboard OK" || echo "✗ Dashboard KO"

# 4. Test RAG (nécessite données)
curl -s -X POST http://localhost:8001/minimee/message \
  -H "Content-Type: application/json" \
  -d '{"content":"test","sender":"user","timestamp":"2024-01-01T10:00:00Z","user_id":1,"source":"dashboard"}' | grep -q "options" && echo "✓ RAG OK" || echo "✗ RAG KO"

# 5. Test metrics
curl -s http://localhost:8001/metrics | grep -q "rag" && echo "✓ Metrics OK" || echo "✗ Metrics KO"

# 6. Vérifier bridge
docker logs --tail 5 minimee-bridge 2>&1 | grep -q "connected\|QR" && echo "✓ Bridge OK" || echo "✗ Bridge KO"
```

---

## 🐛 Résolution de Problèmes

### Backend ne répond pas
```bash
# Vérifier les logs
docker logs minimee-backend

# Vérifier la connexion DB
docker exec minimee-backend python -c "from db.database import engine; engine.connect()"
```

### Dashboard ne se charge pas
```bash
# Vérifier les logs
docker logs minimee-dashboard

# Vérifier node_modules
docker exec minimee-dashboard ls -la node_modules | head -5
```

### Bridge WhatsApp ne se connecte pas
```bash
# Vérifier les logs détaillés
docker logs minimee-bridge | tail -50

# Vérifier auth_info
docker exec minimee-bridge ls -la /app/auth_info 2>&1
```

### RAG ne retourne pas de résultats
```bash
# Vérifier les données dans la DB
docker exec minimee-postgres psql -U minimee -d minimee \
  -c "SELECT COUNT(*) FROM embeddings;"

# Seed la DB si vide
make seed
```

---

## ✅ Critères de Succès

Pour considérer que tout fonctionne :
- ✅ Tous les conteneurs sont "running"
- ✅ `curl http://localhost:8001/health` retourne `{"status":"ok"}`
- ✅ Dashboard accessible sur http://localhost:3002
- ✅ Page Minimee affiche le dialog A/B/C
- ✅ Un message test génère 3 options de réponse
- ✅ L'approbation d'une option fonctionne
- ✅ WhatsApp bridge logue "WhatsApp connected"
- ✅ Gmail OAuth fonctionne (si configuré)
- ✅ Agents CRUD fonctionne dans le dashboard

**Une fois tous ces tests passés, Minimee est prêt pour la démo ! 🎉**

