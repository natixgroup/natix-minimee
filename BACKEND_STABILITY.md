# 🔒 Backend Stability - Mesures de Protection

Ce document décrit les mesures mises en place pour garantir la stabilité du backend et éviter les pannes.

## 🛡️ Protections Mises en Place

### 1. Validation de Syntaxe Python

#### Script de Validation (`apps/backend/scripts/validate_syntax.py`)
- Valide la syntaxe de tous les fichiers Python avant le démarrage
- Utilise `ast.parse()` pour détecter les erreurs de syntaxe
- Exclut automatiquement `__pycache__`, `.venv`, `node_modules`

#### Intégration dans Docker Compose
Le backend valide maintenant la syntaxe avant de démarrer :
```yaml
command: bash -c "python3 scripts/validate_syntax.py && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
```

**Avantage** : Le container ne démarre pas si une erreur de syntaxe est détectée, évitant les pannes silencieuses.

### 2. Validation au Startup (`main.py`)

Le `startup_event()` valide maintenant :
- ✅ Syntaxe Python de tous les routers
- ✅ Connexion à la base de données
- ✅ Extension pgvector

**Avantage** : Détection précoce des erreurs avant que le serveur ne soit considéré comme "prêt".

### 3. Healthcheck Amélioré (`/health`)

Le endpoint `/health` vérifie maintenant :
- ✅ Connexion à la base de données
- ✅ Import des modules principaux (détecte les erreurs de syntaxe runtime)
- ✅ Retourne des messages d'erreur détaillés avec type d'erreur

**Avantage** : Docker peut détecter automatiquement les problèmes et redémarrer le container.

### 4. Pre-commit Hook Git

Un hook Git valide la syntaxe avant chaque commit :
- Fichier : `.git/hooks/pre-commit`
- Valide uniquement les fichiers Python modifiés
- Empêche les commits avec des erreurs de syntaxe

**Avantage** : Les erreurs de syntaxe sont détectées avant même d'être commitées.

### 5. Configuration Docker

#### Healthcheck Configuré
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

#### Restart Policy
```yaml
restart: unless-stopped
```

**Avantage** : Le container redémarre automatiquement en cas de crash.

### 6. Gestion des Connexions DB

#### Pool de Connexions Amélioré
- `pool_recycle=3600` : Recyclage des connexions après 1h
- `pool_timeout=30` : Timeout pour obtenir une connexion
- `connect_timeout=10` : Timeout de connexion PostgreSQL
- `statement_timeout=30000` : Timeout des requêtes SQL (30s)

**Avantage** : Évite les connexions obsolètes et les timeouts infinis.

#### Fermeture Correcte des Sessions
- Toutes les sessions DB sont maintenant fermées correctement dans des blocs `try/finally`
- Le middleware utilise maintenant correctement le générateur `get_db()`

**Avantage** : Évite les fuites de connexions qui peuvent bloquer le pool.

## 🔍 Diagnostic

### Vérifier l'État du Backend

```bash
# Vérifier les logs
docker logs --tail 50 minimee-backend

# Vérifier le healthcheck
curl http://localhost:8001/health

# Vérifier la syntaxe manuellement
cd apps/backend && python3 scripts/validate_syntax.py
```

### Vérifier les Connexions DB

```bash
# Vérifier les connexions actives
docker exec minimee-postgres psql -U minimee -d minimee -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'minimee';"
```

## 🚨 En Cas de Problème

### Backend Ne Démarre Pas

1. **Vérifier les logs** :
   ```bash
   docker logs minimee-backend
   ```

2. **Vérifier la syntaxe** :
   ```bash
   cd apps/backend && python3 scripts/validate_syntax.py
   ```

3. **Vérifier les variables d'environnement** :
   ```bash
   docker exec minimee-backend env | grep -E "(DATABASE|GMAIL|LLM)"
   ```

### Backend Répond Mais Erreurs

1. **Vérifier le healthcheck** :
   ```bash
   curl http://localhost:8001/health
   ```

2. **Vérifier les connexions DB** :
   ```bash
   docker exec minimee-postgres psql -U minimee -d minimee -c "SELECT count(*) FROM pg_stat_activity;"
   ```

3. **Redémarrer le backend** :
   ```bash
   docker restart minimee-backend
   ```

## 📋 Checklist de Maintenance

- [ ] Vérifier les logs régulièrement : `docker logs --tail 100 minimee-backend`
- [ ] Tester le healthcheck : `curl http://localhost:8001/health`
- [ ] Vérifier la syntaxe avant de commit : Le pre-commit hook le fait automatiquement
- [ ] Surveiller les connexions DB : Vérifier qu'elles ne s'accumulent pas
- [ ] Mettre à jour les dépendances régulièrement

## 🔄 Améliorations Futures Possibles

1. **Monitoring** : Intégrer Prometheus/Grafana pour surveiller les métriques
2. **Alertes** : Configurer des alertes sur les erreurs critiques
3. **Tests Automatiques** : Ajouter des tests CI/CD qui valident la syntaxe
4. **Rate Limiting** : Ajouter du rate limiting pour éviter la surcharge
5. **Circuit Breaker** : Implémenter un circuit breaker pour les appels externes

## 📝 Notes

- Le script `validate_syntax.py` peut être exécuté manuellement à tout moment
- Le pre-commit hook peut être désactivé temporairement en le renommant
- Le healthcheck Docker peut être ajusté selon les besoins (interval, timeout, retries)

---

**Dernière mise à jour** : Après correction des problèmes de stabilité backend
**Maintenu par** : Équipe Minimee

