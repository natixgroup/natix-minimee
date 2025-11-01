# Guide de Test du Backend Minimee

Guide pratique pour tester tous les endpoints de l'API backend Minimee.

## 🚀 Démarrage Rapide

```bash
# Vérifier que le backend est démarré
curl http://localhost:8001/health
# Réponse attendue: {"status":"ok"}
```

---

## 📋 Tests par Endpoint

### 1. Health Check

```bash
# Test simple
curl http://localhost:8001/health

# Avec verbose (voir headers)
curl -v http://localhost:8001/health

# Réponse attendue:
# {"status":"ok"}
```

### 2. Root Endpoint

```bash
curl http://localhost:8001/

# Réponse attendue:
# {"message":"Minimee API","status":"running","version":"0.1.0"}
```

---

## 🤖 Agents

### Créer un Agent

```bash
curl -X POST http://localhost:8001/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Assistant Test",
    "role": "Customer Support",
    "prompt": "You are a helpful assistant",
    "style": "Professional and friendly",
    "enabled": true,
    "user_id": 1
  }'
```

### Lister tous les Agents

```bash
curl "http://localhost:8001/agents?user_id=1"
```

### Récupérer un Agent par ID

```bash
# Remplacez <id> par l'ID réel
curl "http://localhost:8001/agents/<id>"
```

### Mettre à jour un Agent

```bash
# Remplacez <id> par l'ID réel
curl -X PUT http://localhost:8001/agents/<id> \
  -H "Content-Type: application/json" \
  -d '{
    "style": "Updated style"
  }'
```

### Supprimer un Agent

```bash
# Remplacez <id> par l'ID réel
curl -X DELETE http://localhost:8001/agents/<id>
```

---

## 💬 Minimee Message & Approval

### Envoyer un message (génère options A/B/C)

```bash
curl -X POST http://localhost:8001/minimee/message \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Bonjour, comment ça va ?",
    "sender": "User",
    "timestamp": "2024-01-01T10:00:00Z",
    "conversation_id": "test_001",
    "user_id": 1,
    "source": "dashboard"
  }'
```

**Réponse attendue:**
```json
{
  "message_id": 123,
  "conversation_id": "test_001",
  "options": [
    "Réponse A...",
    "Réponse B...",
    "Réponse C..."
  ]
}
```

### Approuver une réponse

```bash
# Remplacez <message_id> et <option_index> (0, 1, ou 2)
curl -X POST http://localhost:8001/minimee/approve \
  -H "Content-Type: application/json" \
  -d '{
    "message_id": <message_id>,
    "option_index": 0,
    "action": "yes",
    "type": "whatsapp_message"
  }'
```

### Rejeter une réponse

```bash
curl -X POST http://localhost:8001/minimee/approve \
  -H "Content-Type: application/json" \
  -d '{
    "message_id": <message_id>,
    "action": "no",
    "type": "whatsapp_message"
  }'
```

---

## 📧 Gmail

### Vérifier le statut Gmail

```bash
curl "http://localhost:8001/gmail/status?user_id=1"
```

### Démarrer OAuth Gmail

```bash
curl "http://localhost:8001/auth/gmail/start?user_id=1"
```

### Fetch Gmail threads (nécessite OAuth configuré)

```bash
curl "http://localhost:8001/gmail/fetch?days=30&only_replied=true&user_id=1"
```

### Proposer des drafts email

```bash
curl -X POST http://localhost:8001/minimee/email-draft \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "gmail_thread_123",
    "user_id": 1
  }'
```

---

## 📊 Settings

### Récupérer les settings

```bash
curl "http://localhost:8001/settings?user_id=1"
```

### Créer/Mettre à jour un setting

```bash
curl -X POST http://localhost:8001/settings \
  -H "Content-Type: application/json" \
  -d '{
    "key": "llm_provider",
    "value": {"provider": "ollama", "model": "llama2"},
    "user_id": 1
  }'
```

---

## 📜 Policy

### Récupérer les policies

```bash
curl "http://localhost:8001/policy?user_id=1"
```

### Créer/Mettre à jour une policy

```bash
curl -X POST http://localhost:8001/policy \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Policy",
    "rules": {"max_length": 200, "tone": "professional"},
    "user_id": 1
  }'
```

---

## 📝 Prompts

### Lister les prompts

```bash
curl "http://localhost:8001/prompts?user_id=1"
```

### Créer un prompt

```bash
curl -X POST http://localhost:8001/prompts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Prompt",
    "content": "You are a helpful assistant",
    "user_id": 1
  }'
```

---

## 📥 Ingestion (WhatsApp)

### Uploader un fichier WhatsApp

```bash
# Nécessite un fichier .txt WhatsApp
curl -X POST http://localhost:8001/ingest/whatsapp-upload \
  -F "file=@/path/to/whatsapp_export.txt" \
  -F "user_id=1"
```

---

## 📊 Logs

### Récupérer les logs

```bash
# Tous les logs
curl "http://localhost:8001/logs"

# Avec filtres
curl "http://localhost:8001/logs?level=ERROR&service=api&limit=10"
```

---

## 📈 Metrics

### Récupérer les métriques

```bash
curl "http://localhost:8001/metrics"
```

### Métriques filtrées

```bash
curl "http://localhost:8001/metrics?service=llm_metrics&limit=50"
```

---

## 🧪 Script de Test Complet

Créez un fichier `test_backend.sh` :

```bash
#!/bin/bash

BASE_URL="http://localhost:8001"

echo "=== Test Health ==="
curl -s "$BASE_URL/health" | jq .

echo -e "\n=== Test Root ==="
curl -s "$BASE_URL/" | jq .

echo -e "\n=== Test Agents ==="
curl -s "$BASE_URL/agents?user_id=1" | jq .

echo -e "\n=== Test Settings ==="
curl -s "$BASE_URL/settings?user_id=1" | jq .

echo -e "\n=== Test Logs ==="
curl -s "$BASE_URL/logs?limit=5" | jq .

echo -e "\n=== Test Metrics ==="
curl -s "$BASE_URL/metrics?limit=5" | jq .
```

**Utilisation:**
```bash
chmod +x test_backend.sh
./test_backend.sh
```

---

## 🔧 Tests avec jq (pretty JSON)

Si vous avez `jq` installé :

```bash
# Installer jq sur macOS
brew install jq

# Utiliser avec curl
curl -s http://localhost:8001/agents?user_id=1 | jq .
```

---

## 🌐 Interface Swagger/OpenAPI

Pour une interface graphique interactive :

```bash
# Ouvrir dans le navigateur
open http://localhost:8001/docs

# OU
open http://localhost:8001/redoc
```

L'interface Swagger permet de :
- ✅ Voir tous les endpoints
- ✅ Tester directement depuis le navigateur
- ✅ Voir les schémas de requête/réponse
- ✅ Essayer les requêtes avec les bons formats

---

## 🐛 Debugging

### Voir les logs du backend en temps réel

```bash
docker logs -f minimee-backend
```

### Vérifier les erreurs

```bash
docker logs minimee-backend 2>&1 | grep -i error
```

### Test avec verbose pour voir les headers

```bash
curl -v http://localhost:8001/health
```

### Vérifier la connexion DB

```bash
docker exec minimee-backend python -c "from db.database import engine; engine.connect(); print('DB OK')"
```

---

## ✅ Checklist de Test Rapide

```bash
# 1. Health
curl -s http://localhost:8001/health | grep -q "ok" && echo "✅ Health OK" || echo "❌ Health KO"

# 2. Root
curl -s http://localhost:8001/ | grep -q "Minimee" && echo "✅ Root OK" || echo "❌ Root KO"

# 3. Agents
curl -s "http://localhost:8001/agents?user_id=1" | grep -q "\[\|{" && echo "✅ Agents OK" || echo "❌ Agents KO"

# 4. Metrics
curl -s "http://localhost:8001/metrics" | grep -q "\[\|{" && echo "✅ Metrics OK" || echo "❌ Metrics KO"
```

---

## 📚 Exemples de Requêtes Complètes

### Test End-to-End : Message → Approval

```bash
# 1. Envoyer un message
RESPONSE=$(curl -s -X POST http://localhost:8001/minimee/message \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Hello Minimee!",
    "sender": "Test User",
    "timestamp": "2024-01-01T10:00:00Z",
    "user_id": 1,
    "source": "dashboard"
  }')

echo "Réponse: $RESPONSE"

# 2. Extraire message_id (nécessite jq)
MESSAGE_ID=$(echo $RESPONSE | jq -r '.message_id')
echo "Message ID: $MESSAGE_ID"

# 3. Approuver l'option A
curl -X POST http://localhost:8001/minimee/approve \
  -H "Content-Type: application/json" \
  -d "{
    \"message_id\": $MESSAGE_ID,
    \"option_index\": 0,
    \"action\": \"yes\",
    \"type\": \"whatsapp_message\"
  }"
```

---

**Bon test ! 🚀**

