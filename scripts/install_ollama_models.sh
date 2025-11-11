#!/bin/bash
# Script d'installation des modèles Ollama recommandés pour Minimee
# Les modèles sont installés sur l'hôte (pas dans Docker)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODELS_CONFIG="$PROJECT_ROOT/scripts/ollama-models.json"

# Couleurs pour les messages
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧠 Installation des modèles Ollama pour Minimee${NC}"
echo ""

# Vérifier que Ollama est installé
if ! command -v ollama &> /dev/null; then
    echo -e "${RED}❌ Ollama n'est pas installé${NC}"
    echo "Installez Ollama depuis https://ollama.com"
    exit 1
fi

# Vérifier que Ollama est en cours d'exécution
if ! ollama list &> /dev/null; then
    echo -e "${YELLOW}⚠️  Ollama ne semble pas être en cours d'exécution${NC}"
    echo "Démarrez Ollama et réessayez"
    exit 1
fi

echo -e "${GREEN}✓ Ollama est installé et fonctionne${NC}"
echo ""

# Lire la configuration JSON
if [ ! -f "$MODELS_CONFIG" ]; then
    echo -e "${RED}❌ Fichier de configuration non trouvé: $MODELS_CONFIG${NC}"
    exit 1
fi

# Vérifier que jq est installé (pour parser JSON)
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}⚠️  jq n'est pas installé, installation via Homebrew...${NC}"
    if command -v brew &> /dev/null; then
        brew install jq
    else
        echo -e "${RED}❌ jq est requis pour ce script. Installez-le avec: brew install jq${NC}"
        exit 1
    fi
fi

# Afficher les modèles à installer
echo -e "${BLUE}Modèles à installer :${NC}"
jq -r '.required_models[] | "  - \(.name) (\(.size)) - \(.description)"' "$MODELS_CONFIG"
echo ""

# Calculer la taille totale
TOTAL_SIZE=$(jq -r '.total_size_gb' "$MODELS_CONFIG")
echo -e "${BLUE}Taille totale estimée : ~${TOTAL_SIZE} GB${NC}"
echo ""

# Vérifier l'espace disque disponible (au moins 5 GB recommandés)
echo "Vérification de l'espace disque..."
if command -v df &> /dev/null; then
    AVAILABLE_SPACE_STR=$(df -h . | awk 'NR==2 {print $4}')
    # Extraire le nombre (supprimer G, M, etc.)
    AVAILABLE_SPACE=$(echo "$AVAILABLE_SPACE_STR" | sed 's/[^0-9.]//g' | cut -d. -f1)
    
    if [ -n "$AVAILABLE_SPACE" ] && [ "$AVAILABLE_SPACE" -lt 5 ]; then
        echo -e "${YELLOW}⚠️  Attention: Moins de 5 GB d'espace disponible (${AVAILABLE_SPACE_STR})${NC}"
        read -p "Continuer quand même? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo -e "${GREEN}✓ Espace disque suffisant (${AVAILABLE_SPACE_STR} disponible)${NC}"
    fi
fi

echo ""

# Vérifier les modèles déjà installés
echo "Vérification des modèles déjà installés..."
INSTALLED_MODELS=$(ollama list 2>/dev/null | awk 'NR>1 {print $1}' || echo "")

# Installer chaque modèle
FAILED_MODELS=()
jq -r '.required_models[].name' "$MODELS_CONFIG" | while read -r model; do
    # Vérifier si le modèle est déjà installé
    if echo "$INSTALLED_MODELS" | grep -q "^${model}$"; then
        echo -e "${GREEN}✓ $model est déjà installé${NC}"
        continue
    fi
    
    echo ""
    echo -e "${BLUE}📥 Installation de $model...${NC}"
    
    if ollama pull "$model"; then
        echo -e "${GREEN}✓ $model installé avec succès${NC}"
    else
        echo -e "${RED}❌ Erreur lors de l'installation de $model${NC}"
        FAILED_MODELS+=("$model")
    fi
done

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ ${#FAILED_MODELS[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ Installation terminée avec succès!${NC}"
    echo ""
    echo "Modèles installés :"
    ollama list
else
    echo -e "${YELLOW}⚠️  Installation terminée avec des erreurs${NC}"
    echo "Modèles en échec : ${FAILED_MODELS[*]}"
    echo ""
    echo "Modèles actuellement installés :"
    ollama list
    exit 1
fi


