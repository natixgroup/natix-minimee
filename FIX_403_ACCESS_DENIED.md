# 🔧 Fix : Error 403: access_denied

## Problème
Vous rencontrez l'erreur :
```
Error 403: access_denied
Minimee has not completed the Google verification process.
The app is currently being tested, and can only be accessed by developer-approved testers.
```

## Solution : Ajouter votre email aux utilisateurs test

### Étapes détaillées :

1. **Aller dans Google Cloud Console**
   - Ouvrez : https://console.cloud.google.com/
   - Sélectionnez votre projet "Minimee AI Agent" (ou le nom que vous avez donné)

2. **Accéder à l'écran de consentement OAuth**
   - Menu ☰ > **APIs & Services** > **OAuth consent screen**
   - Ou directement : https://console.cloud.google.com/apis/credentials/consent

3. **Ajouter votre email aux utilisateurs test**
   - Faites défiler jusqu'à la section **"Test users"** (Utilisateurs test)
   - Cliquez sur **"+ ADD USERS"** (+ AJOUTER DES UTILISATEURS)
   - Entrez votre adresse Gmail complète (ex: `votre.email@gmail.com`)
   - Cliquez sur **"ADD"** (AJOUTER)
   - ⚠️ **Important** : Utilisez exactement l'email que vous utiliserez pour vous connecter

4. **Sauvegarder**
   - Cliquez sur **"SAVE"** (ENREGISTRER) en bas de la page
   - Attendez quelques secondes pour que les changements soient pris en compte

5. **Réessayer la connexion**
   - Retournez sur : http://localhost:3002/settings
   - Onglet "Gmail" > Cliquez sur "Connect Gmail"
   - Vous devriez maintenant pouvoir vous connecter !

## ⚠️ Notes importantes

- **L'email doit correspondre exactement** à celui que vous utilisez pour vous connecter à Google
- Les changements peuvent prendre quelques secondes à être actifs
- Vous pouvez ajouter jusqu'à **100 utilisateurs test** dans une application de test
- Pour plus de 100 utilisateurs, vous devrez soumettre l'application pour vérification Google

## Vérification

Si après avoir ajouté votre email, vous voyez toujours l'erreur :
1. Vérifiez que vous avez bien sauvegardé les changements dans Google Cloud Console
2. Vérifiez que l'email correspond exactement (casse, espaces, etc.)
3. Attendez 1-2 minutes et réessayez
4. Videz le cache du navigateur et réessayez

## Alternative : Publier l'application (non recommandé pour dev)

Si vous voulez que tous les utilisateurs puissent accéder sans être dans la liste :
1. Dans "OAuth consent screen", changez le mode de "Testing" à "In production"
2. ⚠️ **Attention** : Cela nécessite une vérification Google complète (peut prendre des semaines)
3. ⚠️ Pour le développement, il est recommandé de rester en mode "Testing"
