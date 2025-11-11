# 🚀 Configuration Rapide Gmail

## Problème : "Gmail OAuth credentials not configured"

Cette erreur signifie que les credentials Gmail (client_id et client_secret) ne sont pas configurés.

## Solution Rapide

### Option 1 : Via l'API (Recommandé)

Utilisez l'endpoint Settings pour configurer les credentials. Le `value` doit être un objet JSON :

```bash
# Configurer gmail_client_id
curl -X POST http://localhost:8001/settings \
  -H "Content-Type: application/json" \
  -d '{
    "key": "gmail_client_id",
    "value": {"client_id": "VOTRE_CLIENT_ID_ICI"},
    "user_id": null
  }'

# Configurer gmail_client_secret
curl -X POST http://localhost:8001/settings \
  -H "Content-Type: application/json" \
  -d '{
    "key": "gmail_client_secret",
    "value": {"client_secret": "VOTRE_CLIENT_SECRET_ICI"},
    "user_id": null
  }'
```

**Note** : Le code gère aussi les strings simples stockées dans la DB, mais le schéma API attend un objet JSON. Pour une string simple, utilisez :
```bash
# Format string (si stocké comme string dans la DB)
curl -X POST http://localhost:8001/settings \
  -H "Content-Type: application/json" \
  -d '{
    "key": "gmail_client_id",
    "value": {"value": "VOTRE_CLIENT_ID_ICI"},
    "user_id": null
  }'
```

**Recommandation** : Utilisez le format avec `{"client_id": "..."}` ou `{"client_secret": "..."}` pour plus de clarté.

### Option 2 : Via Variables d'Environnement

1. Créez ou modifiez le fichier `.env` à la racine du projet :

```dotenv
GMAIL_CLIENT_ID="votre-client-id-google.apps.googleusercontent.com"
GMAIL_CLIENT_SECRET="GOCSPX-votre-client-secret"
GMAIL_REDIRECT_URI="http://localhost:3002/auth/gmail/callback"
```

2. Redémarrez le backend :

```bash
docker restart minimee-backend
```

### Option 3 : Via Docker Compose

Modifiez `infra/docker/docker-compose.yml` et ajoutez les variables directement :

```yaml
environment:
  - GMAIL_CLIENT_ID="votre-client-id"
  - GMAIL_CLIENT_SECRET="votre-client-secret"
```

Puis redémarrez :

```bash
cd infra/docker && docker-compose restart backend
```

## Vérifier la Configuration

```bash
# Vérifier le statut Gmail
curl http://localhost:8001/gmail/status

# Devrait retourner :
# {
#   "connected": false,
#   "has_token": false,
#   "has_client_credentials": true,  # ← Doit être true
#   "has_refresh_token": false
# }
```

## Obtenir les Credentials Google

Si vous n'avez pas encore les credentials :

1. Allez sur [Google Cloud Console](https://console.cloud.google.com/)
2. Créez un projet ou sélectionnez-en un
3. Activez l'API Gmail
4. Créez des identifiants OAuth 2.0
5. Configurez l'écran de consentement OAuth
6. Copiez le Client ID et Client Secret

**Guide complet** : Voir `GUIDE_GMAIL_OAUTH.md`

## Après Configuration

Une fois les credentials configurés :

1. Vérifiez le statut : `curl http://localhost:8001/gmail/status`
2. Connectez Gmail via l'UI ou l'API :
   ```bash
   curl "http://localhost:8001/auth/gmail/start?user_id=1"
   ```
3. Suivez le flux OAuth dans votre navigateur

## Dépannage

### Les credentials ne sont pas pris en compte

1. Vérifiez que vous avez redémarré le backend après modification
2. Vérifiez les logs : `docker logs minimee-backend | grep -i gmail`
3. Vérifiez les variables d'environnement dans le container :
   ```bash
   docker exec minimee-backend env | grep GMAIL
   ```

### Erreur "redirect_uri_mismatch"

Vérifiez que dans Google Cloud Console, l'URI de redirection autorisé est exactement :
```
http://localhost:3002/auth/gmail/callback
```

### Les credentials sont masqués dans l'API

C'est normal pour la sécurité. Utilisez l'endpoint POST pour les configurer, pas GET.

---

**Besoin d'aide ?** Consultez `GUIDE_GMAIL_OAUTH.md` pour un guide détaillé.

