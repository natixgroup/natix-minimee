#!/bin/bash
# Script pour vérifier que "use client" est en première ligne dans les fichiers frontend Next.js

echo "🔍 Vérification des directives 'use client' dans les fichiers frontend..."

ERRORS=0

# Chercher tous les fichiers .tsx et .ts dans app/ qui contiennent "use client"
find apps/dashboard/app -type f \( -name "*.tsx" -o -name "*.ts" \) | while read file; do
    if grep -q "use client" "$file"; then
        # Vérifier que "use client" est en première ligne (ignorant les lignes vides)
        first_non_empty=$(grep -n "." "$file" | head -1 | cut -d: -f1)
        first_line_content=$(sed -n "${first_non_empty}p" "$file")
        
        if [[ ! "$first_line_content" =~ "use client" ]]; then
            echo "❌ ERREUR: $file"
            echo "   La directive 'use client' n'est pas en première ligne"
            echo "   Première ligne non-vide: $first_line_content"
            ERRORS=$((ERRORS + 1))
        fi
    fi
done

if [ $ERRORS -eq 0 ]; then
    echo "✅ Tous les fichiers sont corrects"
    exit 0
else
    echo "❌ $ERRORS erreur(s) trouvée(s)"
    exit 1
fi





