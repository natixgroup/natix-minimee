# Guide de Test du Frontend Minimee (Dashboard)

Guide pratique pour tester toutes les fonctionnalités du dashboard Next.js.

## 🚀 Accès Rapide

### 1. Ouvrir le Dashboard

```bash
# Ouvrir dans le navigateur
open http://localhost:3002

# OU manuellement
# Naviguer vers: http://localhost:3002
```

### 2. Vérifier que le dashboard répond

```bash
curl -I http://localhost:3002
# Attendu: HTTP/1.1 200 OK
```

**⚠️ Note:** Si le port 3000 est occupé par un autre projet, le dashboard Minimee ne pourra pas démarrer. Vérifiez avec:
```bash
lsof -i :3000
```

---

## 📋 Tests par Page

### 1. Page Overview (Home)

**URL:** http://localhost:3000/

**À vérifier:**
- ✅ La page se charge sans erreur
- ✅ Les cartes statistiques s'affichent
- ✅ Pas d'erreurs dans la console (F12 → Console)

**Test:**
1. Ouvrir http://localhost:3002/
2. Vérifier l'absence d'erreurs dans la console navigateur (F12)
3. Les cartes devraient afficher des statistiques (même si à 0)

---

### 2. Page Minimee (A/B/C Approval)

**URL:** http://localhost:3002/minimee

**Fonctionnalités à tester:**

#### A. Envoyer un message

1. Taper un message dans le champ texte
   - Exemple: "Hello, how are you?"
2. Cliquer sur "Process Message"
3. **Vérifier:**
   - ✅ Un dialog s'ouvre avec 3 options (A, B, C)
   - ✅ Chaque option affiche une réponse différente
   - ✅ Les options sont sélectionnables (cliquer dessus)

#### B. Approuver une option

1. Sélectionner l'option A (ou B/C)
   - La bordure devient bleue
2. Cliquer sur "Approve Option A"
3. **Vérifier:**
   - ✅ Une notification toast apparaît: "Response approved and sent!"
   - ✅ Le dialog se ferme
   - ✅ Le message apparaît dans la liste (si implémenté)

#### C. Rejeter toutes les options

1. Envoyer un nouveau message
2. Cliquer sur "Reject All" (sans sélectionner)
3. **Vérifier:**
   - ✅ Notification: "Response rejected"
   - ✅ Le dialog se ferme

**Test via Console Navigateur:**
```javascript
// Vérifier que l'API est accessible
fetch('http://localhost:8001/health')
  .then(r => r.json())
  .then(data => console.log('Backend OK:', data))
  .catch(e => console.error('Backend KO:', e));
```

---

### 3. Page Agents

**URL:** http://localhost:3002/agents

**Fonctionnalités à tester:**

#### A. Lister les agents

1. Aller sur http://localhost:3002/agents
2. **Vérifier:**
   - ✅ Une table/listaffiche les agents
   - ✅ Les agents existants sont visibles
   - ✅ Colonnes: Name, Role, Enabled, Actions

#### B. Créer un agent

1. Cliquer sur "Create Agent" ou "+ New Agent"
2. Remplir le formulaire:
   - Name: "Test Agent"
   - Role: "Customer Support"
   - Prompt: "You are a helpful customer support agent"
   - Style: "Professional and friendly"
   - Enabled: ✓ (checkbox)
3. Cliquer sur "Create Agent" ou "Save"
4. **Vérifier:**
   - ✅ Notification de succès
   - ✅ L'agent apparaît dans la liste
   - ✅ L'agent est éditable

#### C. Modifier un agent

1. Cliquer sur un agent dans la liste
2. Modifier un champ (ex: changer le style)
3. Cliquer sur "Update Agent"
4. **Vérifier:**
   - ✅ Notification de succès
   - ✅ Les changements sont sauvegardés
   - ✅ L'agent affiche les nouvelles valeurs

#### D. Désactiver/Activer un agent

1. Cliquer sur un agent
2. Décocher "Enabled"
3. Sauvegarder
4. **Vérifier:**
   - ✅ L'agent n'apparaît plus comme actif
   - ✅ Le badge "Enabled" change

#### E. Supprimer un agent

1. Cliquer sur "Delete" ou l'icône poubelle
2. Confirmer la suppression
3. **Vérifier:**
   - ✅ Notification de succès
   - ✅ L'agent disparaît de la liste

---

### 4. Page Logs

**URL:** http://localhost:3002/logs

**Fonctionnalités à tester:**

#### A. Afficher les logs

1. Aller sur http://localhost:3002/logs
2. **Vérifier:**
   - ✅ Un tableau affiche les logs
   - ✅ Colonnes: Level, Message, Service, Timestamp
   - ✅ Les logs sont triés par date (plus récents en haut)

#### B. Filtrer les logs

1. Utiliser les filtres (si disponibles):
   - Par niveau: ERROR, WARNING, INFO
   - Par service: api, llm_metrics, etc.
   - Par date
2. **Vérifier:**
   - ✅ Les logs sont filtrés correctement
   - ✅ Le compteur se met à jour

#### C. Pagination

1. Si beaucoup de logs, vérifier:
   - ✅ La pagination fonctionne
   - ✅ Les boutons Next/Previous fonctionnent

---

### 5. Page Settings

**URL:** http://localhost:3002/settings

**Fonctionnalités à tester:**

#### A. Onglet General

1. Aller sur http://localhost:3002/settings
2. **Vérifier:**
   - ✅ Les paramètres actuels s'affichent
   - ✅ Les champs sont éditables

#### B. Onglet LLM Provider

1. Cliquer sur l'onglet "LLM"
2. **Vérifier:**
   - ✅ Sélecteur de provider: Ollama, vLLM, OpenAI
   - ✅ Champ pour l'URL/base (si Ollama/vLLM)
   - ✅ Champ pour API Key (si OpenAI)
3. Changer le provider et sauvegarder
4. **Vérifier:**
   - ✅ Le changement est sauvegardé
   - ✅ Notification de succès

#### C. Onglet Embeddings

1. Cliquer sur l'onglet "Embeddings"
2. **Vérifier:**
   - ✅ Modèle d'embedding affiché
   - ✅ Dimension affichée (384 par défaut)
   - ✅ Possibilité de changer le modèle

#### D. Onglet WhatsApp

1. Cliquer sur l'onglet "WhatsApp"
2. **Tester l'upload:**
   - Cliquer sur "Choose File" ou drag & drop
   - Sélectionner un fichier `.txt` WhatsApp
   - Cliquer sur "Upload"
   - **Vérifier:**
     - ✅ Notification: "WhatsApp file uploaded and processed"
     - ✅ Pas d'erreur dans la console

#### E. Onglet Gmail

1. Cliquer sur l'onglet "Gmail"
2. **Vérifier le statut:**
   - ✅ Badge "Connected" ou "Not Connected"
   - ✅ Bouton "Connect Gmail" visible si non connecté
3. **Tester la connexion OAuth:**
   - Cliquer sur "Connect Gmail"
   - **Vérifier:**
     - ✅ Redirection vers Google OAuth
     - ✅ Après autorisation, redirection vers callback
     - ✅ Badge passe à "Connected"
4. **Tester le fetch:**
   - Cliquer sur "Fetch Recent Emails (30 days)"
   - **Vérifier:**
     - ✅ Notification: "Gmail threads fetched and indexed successfully"
     - ✅ Pas d'erreur dans la console

---

## 🧪 Tests Automatisés (Console Navigateur)

### Ouvrir la Console

**Chrome/Edge:**
- `F12` ou `Cmd+Option+I` (Mac) / `Ctrl+Shift+I` (Windows)

**Firefox:**
- `F12` ou `Cmd+Option+K` (Mac) / `Ctrl+Shift+K` (Windows)

### Tests API depuis la Console

```javascript
// Test 1: Vérifier que le backend est accessible
fetch('http://localhost:8001/health')
  .then(r => r.json())
  .then(data => {
    console.log('✅ Backend Health:', data);
  })
  .catch(e => console.error('❌ Backend Error:', e));

// Test 2: Récupérer les agents
fetch('http://localhost:8001/agents?user_id=1')
  .then(r => r.json())
  .then(data => {
    console.log('✅ Agents:', data);
  })
  .catch(e => console.error('❌ Agents Error:', e));

// Test 3: Envoyer un message
fetch('http://localhost:8001/minimee/message', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    content: "Test message from browser",
    sender: "Browser Test",
    timestamp: new Date().toISOString(),
    user_id: 1,
    source: "dashboard"
  })
})
  .then(r => r.json())
  .then(data => {
    console.log('✅ Message Response:', data);
  })
  .catch(e => console.error('❌ Message Error:', e));
```

---

## 🔍 Vérifications de Qualité

### 1. Console Errors

**À vérifier:**
- ✅ Pas d'erreurs rouges dans la console
- ✅ Pas d'erreurs 404 pour les ressources (images, CSS, JS)
- ✅ Pas d'erreurs CORS

**Actions:**
1. Ouvrir la console (F12)
2. Vérifier l'onglet "Console"
3. Filtrer par "Errors"
4. Aucune erreur ne devrait apparaître

### 2. Network Requests

**À vérifier:**
1. Ouvrir DevTools → Network
2. Recharger la page (F5)
3. **Vérifier:**
   - ✅ Tous les fichiers se chargent (status 200)
   - ✅ Les appels API fonctionnent
   - ✅ Pas de requêtes bloquées (CORS)

### 3. Performance

**À vérifier:**
1. DevTools → Performance ou Lighthouse
2. Lancer un audit
3. **Vérifier:**
   - ✅ Temps de chargement < 3s
   - ✅ Pas de ressources bloquantes

### 4. Responsive Design

**À tester:**
1. DevTools → Toggle Device Toolbar (Cmd+Shift+M)
2. Tester sur:
   - Mobile (375px)
   - Tablet (768px)
   - Desktop (1920px)
3. **Vérifier:**
   - ✅ Le layout s'adapte
   - ✅ Le texte reste lisible
   - ✅ Les boutons sont cliquables

---

## 🎨 Tests UI/UX

### 1. Dark Mode

**À tester:**
1. Chercher le toggle Dark Mode (généralement en haut à droite)
2. Basculer entre Light/Dark
3. **Vérifier:**
   - ✅ Le thème change immédiatement
   - ✅ La préférence est sauvegardée (recharger la page)
   - ✅ Tous les composants respectent le thème

### 2. Navigation

**À tester:**
1. Cliquer sur chaque lien du menu latéral
2. **Vérifier:**
   - ✅ La navigation est fluide
   - ✅ L'URL change correctement
   - ✅ Le menu actif est mis en évidence

### 3. Formulaires

**À tester pour chaque formulaire:**
- ✅ Validation côté client (erreurs affichées)
- ✅ Messages d'erreur clairs
- ✅ Disabled state pendant la soumission
- ✅ Feedback visuel (loading, success, error)

---

## 🐛 Debugging

### Voir les logs du dashboard

```bash
# Logs en temps réel
docker logs -f minimee-dashboard

# Dernières lignes
docker logs --tail 50 minimee-dashboard
```

### Vérifier les erreurs Next.js

1. Ouvrir la console navigateur (F12)
2. Vérifier l'onglet "Console"
3. Chercher les erreurs rouges
4. Copier l'erreur complète pour debugging

### Vérifier la connexion Backend

```javascript
// Dans la console navigateur
fetch('http://localhost:8001/health')
  .then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  })
  .then(data => console.log('✅ Backend accessible:', data))
  .catch(e => console.error('❌ Backend inaccessible:', e));
```

---

## ✅ Checklist Rapide

```bash
# 1. Dashboard accessible
curl -I http://localhost:3002 | grep "200 OK" && echo "✅ Dashboard OK" || echo "❌ Dashboard KO"

# 2. Backend accessible depuis le navigateur
# (Tester dans la console navigateur)
# fetch('http://localhost:8001/health').then(r => r.json()).then(console.log)

# 3. Pas d'erreurs dans les logs
docker logs --tail 20 minimee-dashboard | grep -i error || echo "✅ Pas d'erreurs"
```

---

## 🚨 Problèmes Courants

### Le dashboard ne se charge pas

**Causes possibles:**
1. Port 3000 occupé
   ```bash
   lsof -i :3000
   # Tuer le processus ou changer le port dans docker-compose.yml
   ```

2. Backend non accessible
   ```bash
   curl http://localhost:8001/health
   # Si KO, vérifier que le backend est démarré
   ```

3. Erreurs de build
   ```bash
   docker logs minimee-dashboard | grep -i error
   ```

### Erreurs CORS

**Symptômes:**
- Erreur "CORS policy" dans la console
- Les requêtes API échouent

**Solution:**
- Vérifier que `NEXT_PUBLIC_API_URL` est bien configuré
- Vérifier que le backend autorise les requêtes depuis `localhost:3002`

### Le thème dark ne fonctionne pas

**Solution:**
- Vérifier que `next-themes` est installé
- Vérifier le `ThemeProvider` dans `app/providers.tsx`

---

**Bon test ! 🎨**

