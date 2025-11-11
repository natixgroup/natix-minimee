# 📧 Guide : Configuration Gmail OAuth pour Minimee

Ce guide vous explique étape par étape comment configurer l'intégration Gmail OAuth pour Minimee.

---

## 📋 Prérequis

- Un compte Google (Gmail)
- Accès à [Google Cloud Console](https://console.cloud.google.com/)
- Le projet Minimee en cours d'exécution

---

## 🔧 Étape 1 : Créer un projet Google Cloud Console

### 1.1 Accéder à Google Cloud Console

1. Ouvrez votre navigateur et allez sur [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Connectez-vous avec votre compte Google

### 1.2 Créer un nouveau projet

1. En haut de la page, cliquez sur le **sélecteur de projet** (nom du projet actuel ou "My First Project")
2. Dans la boîte de dialogue, cliquez sur **"Nouveau projet"** (New Project)
3. **Nom du projet** : `Minimee AI Agent` (ou le nom de votre choix)
4. Cliquez sur **"Créer"** (Create)
5. Attendez la création et sélectionnez le projet

---

## 📚 Étape 2 : Activer l'API Gmail

### 2.1 Naviguer vers la bibliothèque d'API

1. Dans le menu de navigation (☰ en haut à gauche), allez à :
   - **"APIs & Services"** > **"Library"** (Bibliothèque)
   - Ou directement : [https://console.cloud.google.com/apis/library](https://console.cloud.google.com/apis/library)

### 2.2 Rechercher et activer Gmail API

1. Dans la barre de recherche, tapez : **"Gmail API"**
2. Cliquez sur le résultat **"Gmail API"**
3. Sur la page de l'API, cliquez sur le bouton **"ACTIVER"** (Enable)
4. Attendez quelques secondes que l'API soit activée

✅ **Vérification** : Vous devriez voir "API enabled" en vert

---

## 🔐 Étape 3 : Configurer l'écran de consentement OAuth

### 3.1 Accéder à la configuration OAuth

1. Dans le menu, allez à : **"APIs & Services"** > **"OAuth consent screen"**
   - Ou directement : [https://console.cloud.google.com/apis/credentials/consent](https://console.cloud.google.com/apis/credentials/consent)

### 3.2 Configuration initiale

1. **Type d'utilisateur** : Choisissez **"Externe"** (External)
   - Sauf si vous avez un compte Google Workspace
2. Cliquez sur **"Créer"** (Create)

### 3.3 Informations sur l'application

Remplissez les champs requis :

- **Nom de l'application** : `Minimee`
- **E-mail d'assistance utilisateur** : Votre adresse e-mail
- **Coordonnées du développeur** : Votre adresse e-mail (peut être la même)

Cliquez sur **"Enregistrer et continuer"** (Save and Continue)

### 3.4 Scopes (Autorisations)

1. Pour l'instant, vous n'avez pas besoin d'ajouter de scopes manuellement
2. Cliquez sur **"Enregistrer et continuer"** (Save and Continue)

> **Note** : Les scopes nécessaires seront automatiquement demandés lors de l'autorisation OAuth.

### 3.5 Utilisateurs test ⚠️ IMPORTANT

1. **Ajoutez votre adresse e-mail Google** pour pouvoir tester l'application :
   - Cliquez sur **"Ajouter des utilisateurs"** (Add users)
   - Entrez votre adresse Gmail complète (ex: `votre.email@gmail.com`)
   - Cliquez sur **"Ajouter"** (Add)
   - Répétez pour chaque adresse email que vous voulez autoriser

2. **⚠️ CRITIQUE** : Sans cette étape, vous obtiendrez l'erreur :
   ```
   Error 403: access_denied
   The app is currently being tested, and can only be accessed by developer-approved testers
   ```

3. Cliquez sur **"Enregistrer et continuer"** (Save and Continue)

### 3.6 Résumé

1. Vérifiez les informations
2. Cliquez sur **"Retour au tableau de bord"** (Back to Dashboard)

---

## 🔑 Étape 4 : Créer les identifiants OAuth 2.0

### 4.1 Accéder aux identifiants

1. Dans le menu, allez à : **"APIs & Services"** > **"Credentials"**
   - Ou directement : [https://console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials)

### 4.2 Créer un ID client OAuth

1. En haut de la page, cliquez sur **"+ CRÉER DES IDENTIFIANTS"** (+ CREATE CREDENTIALS)
2. Sélectionnez **"ID client OAuth"** (OAuth client ID)

### 4.3 Configuration du client

**Type d'application** : Choisissez **"Application Web"** (Web application)

**Nom** : `Minimee Web Client` (ou le nom de votre choix)

#### Origines JavaScript autorisées (Authorized JavaScript origins)

Cliquez sur **"+ AJOUTER UN URI"** (+ ADD URI) et ajoutez :
```
http://localhost:3002
```

#### URI de redirection autorisés (Authorized redirect URIs)

Cliquez sur **"+ AJOUTER UN URI"** (+ ADD URI) et ajoutez :
```
http://localhost:3002/auth/gmail/callback
```

### 4.4 Créer et récupérer les identifiants

1. Cliquez sur **"Créer"** (Create)
2. Une fenêtre modale s'ouvre avec vos identifiants :
   - **ID client** (Client ID)
   - **Clé secrète client** (Client secret)
3. **⚠️ IMPORTANT** : Copiez ces deux valeurs immédiatement, elles ne seront plus affichées !
   - Vous pouvez les télécharger en cliquant sur **"Télécharger JSON"** (Download JSON) si vous préférez

---

## ⚙️ Étape 5 : Configurer Minimee

### 5.1 Localiser le fichier .env

Les variables d'environnement peuvent être dans plusieurs emplacements selon votre configuration :

- `infra/.env`
- `apps/backend/.env`
- `.env` à la racine du projet

### 5.2 Ajouter les variables d'environnement

Ouvrez votre fichier `.env` (créez-le s'il n'existe pas) et ajoutez :

```dotenv
# Gmail OAuth Credentials
GMAIL_CLIENT_ID="VOTRE_ID_CLIENT_GOOGLE_ICI"
GMAIL_CLIENT_SECRET="VOTRE_CLE_SECRETE_CLIENT_ICI"
GMAIL_REDIRECT_URI="http://localhost:3002/auth/gmail/callback"
```

**Remplacez** :
- `VOTRE_ID_CLIENT_GOOGLE_ICI` par l'**ID client** copié à l'étape 4.4
- `VOTRE_CLE_SECRETE_CLIENT_ICI` par la **Clé secrète client** copiée à l'étape 4.4

> **Note** : Les guillemets sont optionnels mais recommandés, surtout si vos valeurs contiennent des caractères spéciaux.

### 5.3 Exemple de fichier .env complet

```dotenv
# Database
DATABASE_URL=postgresql://minimee:minimee@postgres:5432/minimee

# Gmail OAuth Credentials
GMAIL_CLIENT_ID="123456789-abcdefghijklmnop.apps.googleusercontent.com"
GMAIL_CLIENT_SECRET="GOCSPX-abcdefghijklmnopqrstuvwxyz"
GMAIL_REDIRECT_URI="http://localhost:3002/auth/gmail/callback"

# LLM Configuration (exemple)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
```

---

## 🔄 Étape 6 : Redémarrer les services

### 6.1 Redémarrer le backend

Après avoir modifié le fichier `.env`, redémarrez le service backend :

```bash
cd /Users/tarikzouine/git/minimee
docker-compose -f infra/docker/docker-compose.yml restart backend
```

### 6.2 Vérifier que le backend a bien rechargé

```bash
# Vérifier les logs
docker logs --tail 20 minimee-backend

# Vérifier que le service répond
curl http://localhost:8001/health
```

Vous devriez voir `{"status":"ok"}`

---

## ✅ Étape 7 : Tester la connexion Gmail

### 7.1 Accéder au dashboard

1. Ouvrez votre navigateur : [http://localhost:3002](http://localhost:3002)
2. Connectez-vous (si nécessaire)
3. Allez dans **"Settings"** > **"Gmail"**

### 7.2 Cliquer sur "Connect Gmail"

1. Vous devriez voir le bouton **"Connect Gmail"**
2. Cliquez dessus
3. **⚠️ IMPORTANT** : Si vous avez déjà connecté Gmail mais que le refresh_token est manquant, vous devez forcer la ré-autorisation :
   - Utilisez l'URL : `http://localhost:8001/auth/gmail/start?force_consent=true&user_id=1`
   - Ou supprimez le token existant et reconnectez-vous

### 7.3 Autoriser l'accès

1. Vous serez redirigé vers une page Google de demande d'autorisation
2. **⚠️ Si vous voyez "Cette application n'est pas vérifiée"** :
   - C'est normal pour une application en développement
   - Cliquez sur **"Avancé"** (Advanced)
   - Puis sur **"Aller à Minimee (non sécurisé)"** (Go to Minimee (unsafe))
3. Sélectionnez votre compte Google
4. Cliquez sur **"Autoriser"** (Allow)
5. Vous serez redirigé vers : `http://localhost:3002/auth/gmail/callback`

### 7.4 Vérifier la connexion

1. Vous devriez voir un message de succès
2. Redirigé automatiquement vers la page Settings
3. Le statut Gmail devrait maintenant afficher **"Connected"** ✅

---

## 🐛 Résolution de problèmes

### Erreur : "Gmail OAuth credentials not configured"

**Cause** : Les variables d'environnement ne sont pas chargées correctement.

**Solutions** :
1. Vérifiez que le fichier `.env` contient bien les 3 variables :
   - `GMAIL_CLIENT_ID`
   - `GMAIL_CLIENT_SECRET`
   - `GMAIL_REDIRECT_URI`
2. Vérifiez que vous avez bien redémarré le backend :
   ```bash
   docker-compose -f infra/docker/docker-compose.yml restart backend
   ```
3. Vérifiez les logs du backend :
   ```bash
   docker logs minimee-backend | grep -i gmail
   ```

### Erreur : "redirect_uri_mismatch"

**Cause** : L'URI de redirection dans Google Cloud Console ne correspond pas à celui utilisé.

**Solutions** :
1. Vérifiez que dans Google Cloud Console > Credentials > Votre client OAuth :
   - **Authorized redirect URIs** contient exactement : `http://localhost:3002/auth/gmail/callback`
2. Vérifiez que dans votre `.env` :
   - `GMAIL_REDIRECT_URI=http://localhost:3002/auth/gmail/callback`
3. ⚠️ Attention aux espaces et caractères spéciaux !

### Erreur : "access_denied"

**Cause** : L'utilisateur n'a pas autorisé l'application ou n'est pas dans la liste des utilisateurs test.

**Solutions** :
1. Vérifiez que votre adresse Gmail est dans **"OAuth consent screen" > "Test users"**
2. Réessayez l'autorisation

### Erreur : "invalid_client"

**Cause** : L'ID client ou la clé secrète sont incorrects.

**Solutions** :
1. Vérifiez que vous avez copié correctement :
   - **ID client** → `GMAIL_CLIENT_ID`
   - **Clé secrète** → `GMAIL_CLIENT_SECRET`
2. Vérifiez qu'il n'y a pas d'espaces avant/après les valeurs dans `.env`
3. Vérifiez les guillemets : utilisez des guillemets droits `"` et non des guillemets typographiques `"` ou `'`

### Erreur : "The credentials do not contain the necessary fields need to refresh the access token"

**Cause** : Le `refresh_token` est manquant dans la base de données. Google ne renvoie pas toujours un refresh_token lors de l'autorisation OAuth, surtout si l'utilisateur a déjà autorisé l'application précédemment.

**Solutions** :

1. **Ré-authentifier avec force_consent** :
   - Accédez à : `http://localhost:8001/auth/gmail/start?force_consent=true&user_id=1`
   - Ou utilisez l'API directement :
     ```bash
     curl "http://localhost:8001/auth/gmail/start?force_consent=true&user_id=1"
     ```
   - Cela forcera Google à demander à nouveau le consentement et à fournir un refresh_token

2. **Vérifier le refresh_token en base** :
   ```bash
   docker exec minimee-postgres psql -U minimee -d minimee -c "SELECT id, provider, user_id, CASE WHEN refresh_token IS NULL THEN 'NULL' WHEN refresh_token = '' THEN 'EMPTY' ELSE 'HAS_TOKEN' END as refresh_token_status FROM oauth_tokens WHERE provider = 'gmail';"
   ```

3. **Si le refresh_token est toujours NULL après ré-authentification** :
   - Vérifiez que vous utilisez `access_type='offline'` (déjà configuré dans le code)
   - Vérifiez que vous avez bien cliqué sur "Autoriser" et non "Annuler"
   - Essayez de révoquer l'accès dans [Google Account Settings](https://myaccount.google.com/permissions) puis ré-authentifiez

4. **Message d'erreur amélioré** :
   - Le backend affiche maintenant un message clair indiquant quel champ manque
   - Si le refresh_token est manquant, vous verrez : "Gmail refresh_token is missing. Please re-authenticate Gmail to obtain a refresh token."

### Le backend ne charge pas les variables d'environnement

**Solutions** :
1. Vérifiez où Docker cherche le fichier `.env`
   - Selon votre `docker-compose.yml`, il peut être dans `infra/.env` ou ailleurs
2. Utilisez `env_file` dans `docker-compose.yml` :
   ```yaml
   backend:
     env_file:
       - ../.env  # Chemin relatif depuis docker-compose.yml
   ```
3. Redémarrez le conteneur :
   ```bash
   docker-compose -f infra/docker/docker-compose.yml down backend
   docker-compose -f infra/docker/docker-compose.yml up -d backend
   ```

---

## 📝 Notes importantes

### Sécurité

- **⚠️ NE COMMITEZ JAMAIS** votre fichier `.env` dans Git
- Le fichier `.env` devrait être dans `.gitignore`
- Pour la production, utilisez des variables d'environnement sécurisées (AWS Secrets Manager, HashiCorp Vault, etc.)

### Limites de l'application de test

- Les applications en mode "Test" ne peuvent avoir que **100 utilisateurs** maximum
- Pour plus d'utilisateurs, vous devrez **soumettre l'application pour vérification** par Google

### Ports

- Le dashboard Minimee utilise le port **3002** (pas 3000)
- L'URI de redirection doit correspondre exactement : `http://localhost:3002/auth/gmail/callback`

### Production

Pour la production, vous devrez :
1. Changer les URIs autorisés pour votre domaine de production
2. Soumettre l'application pour vérification Google (si > 100 utilisateurs)
3. Utiliser HTTPS (obligatoire pour la production)

---

## 🎉 Félicitations !

Une fois la configuration terminée, vous pouvez :
- ✅ Connecter votre compte Gmail
- ✅ Importer vos conversations Gmail
- ✅ Utiliser Minimee pour générer des réponses d'email

---

## 📚 Ressources supplémentaires

- [Documentation Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
- [Guide Gmail API](https://developers.google.com/gmail/api/guides)
- [Console Google Cloud](https://console.cloud.google.com/)

---

**Besoin d'aide ?** Vérifiez les logs du backend : `docker logs minimee-backend`

