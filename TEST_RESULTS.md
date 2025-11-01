# Résultats des Tests - Minimee

**Date**: $(date)
**Statut**: ⚠️ **PROBLÈMES DÉTECTÉS**

---

## ❌ Problèmes Critiques

### 1. Port 8000 occupé par un autre projet
- **Problème**: Le port 8000 est utilisé par un projet Symfony (lovaconnect)
- **Impact**: Le backend Minimee (FastAPI) ne peut pas démarrer
- **Solutions**:
  - **Option A** (Recommandée): Arrêter le projet lovaconnect
    ```bash
    # Trouver le processus sur le port 8000
    lsof -ti:8000 | xargs kill
    
    # OU trouver le conteneur Docker
    docker ps | grep 8000
    docker stop <container_id>
    ```
  
  - **Option B**: Changer le port Minimee (modifier `infra/docker/docker-compose.yml`)
    ```yaml
    backend:
      ports:
        - "8001:8000"  # Utiliser 8001 au lieu de 8000
    ```
    Puis mettre à jour `.env`:
    ```
    NEXT_PUBLIC_API_URL=http://localhost:8001
    ```

### 2. Build Docker échoué
- **Erreur**: `npm install` échoue dans dashboard et bridge
- **Message**: `npm error enoent An unknown git error occurred`
- **Cause probable**: Problème de permissions ou de cache npm dans Docker
- **Solutions**:
  ```bash
  # Nettoyer le cache Docker
  docker system prune -a --volumes
  
  # Rebuild sans cache
  cd infra/docker
  docker-compose build --no-cache
  
  # OU rebuild seulement dashboard et bridge
  docker-compose build --no-cache dashboard bridge
  ```

### 3. Conteneurs non démarrés
- **Statut**: Aucun conteneur Minimee en cours d'exécution
- **Cause**: Build échoué → conteneurs non créés
- **Action**: Corriger les problèmes ci-dessus puis relancer

---

## ✅ Tests Réussis

1. **Docker installé**: ✅ Version 28.1.1
2. **Docker Compose installé**: ✅ Version v2.35.1
3. **Dashboard accessible**: ✅ Port 3000 répond (mais peut être un autre projet)
4. **Port 5432 libre**: ✅ PostgreSQL peut démarrer

---

## 📋 Checklist de Correction

Pour corriger et relancer les tests :

1. **Libérer le port 8000**
   ```bash
   lsof -ti:8000 | xargs kill -9
   ```

2. **Nettoyer Docker**
   ```bash
   cd /Users/tarikzouine/git/minimee
   docker system prune -a --volumes
   ```

3. **Rebuild les images**
   ```bash
   cd infra/docker
   docker-compose build --no-cache
   ```

4. **Démarrer les services**
   ```bash
   make up
   # OU
   docker-compose up -d
   ```

5. **Vérifier les conteneurs**
   ```bash
   docker ps --filter "name=minimee"
   ```

6. **Attendre le démarrage (30-60 secondes)**
   ```bash
   sleep 30
   ```

7. **Relancer les tests**
   ```bash
   # Test backend
   curl http://localhost:8000/health
   
   # Test dashboard
   curl -I http://localhost:3000
   ```

---

## 🔍 Diagnostic Détaillé

### Logs de Build (extrait)
```
#24 20.53 npm error errno -2
#24 20.53 npm error enoent An unknown git error occurred
#24 20.53 npm error enoent This is related to npm not being able to find a file.
```

### Processus sur Port 8000
- Un projet Symfony (lovaconnect) tourne sur le port 8000
- Ce n'est PAS le backend Minimee FastAPI

### Processus sur Port 3000
- Un serveur répond (peut être Next.js ou autre)

---

## 💡 Recommandations

1. **Immédiat**: Libérer le port 8000
2. **Court terme**: Nettoyer et rebuilder Docker
3. **Long terme**: Utiliser des ports différents pour chaque projet ou un reverse proxy

---

## 📝 Commandes Utiles

```bash
# Voir tous les processus sur les ports
lsof -i :8000
lsof -i :3000
lsof -i :5432

# Voir les conteneurs Docker actifs
docker ps -a

# Voir les logs d'un conteneur
docker logs minimee-backend
docker logs minimee-dashboard
docker logs minimee-bridge

# Nettoyer complètement
make clean
docker system prune -a --volumes

# Rebuild et start
make build
make up
```

---

**Prochaines étapes**: Corriger les problèmes identifiés puis relancer `make up` et les tests.

