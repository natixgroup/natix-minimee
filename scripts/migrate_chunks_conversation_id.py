#!/usr/bin/env python3
"""
Script de migration pour ajouter conversation_id dans les metadata des chunks existants
qui n'ont pas cette information (chunks importés avant la correction RAG)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend'))

from db.database import SessionLocal
from models import Embedding, Message, Summary
from sqlalchemy import text as sql_text
import json

def migrate_chunks():
    """
    Met à jour les chunks existants pour ajouter conversation_id dans leurs metadata
    en utilisant summaries ou messages pour trouver le conversation_id
    """
    db = SessionLocal()
    
    try:
        # Trouver tous les chunks sans conversation_id dans metadata
        query = sql_text("""
            SELECT 
                e.id,
                e.metadata,
                e.text
            FROM embeddings e
            WHERE e.metadata->>'chunk' = 'true'
            AND (e.metadata->>'conversation_id' IS NULL 
                 OR e.metadata->>'conversation_id' = '')
            AND (e.metadata->>'thread_id' IS NULL 
                 OR e.metadata->>'thread_id' = '')
        """)
        
        chunks_to_update = db.execute(query).fetchall()
        print(f"📊 Trouvé {len(chunks_to_update)} chunks sans conversation_id/thread_id")
        
        updated_count = 0
        skipped_count = 0
        
        for chunk_row in chunks_to_update:
            chunk_id = chunk_row.id
            current_metadata = chunk_row.metadata or {}
            
            # Essayer de trouver conversation_id via summaries
            # On cherche un summary dont le texte contient des mots-clés du chunk
            chunk_text_preview = chunk_row.text[:100] if chunk_row.text else ""
            
            # Méthode 1: Chercher via summaries qui pourraient correspondre
            summary = db.query(Summary).filter(
                Summary.summary_text.ilike(f'%{chunk_text_preview[:50]}%')
            ).first()
            
            conversation_id = None
            if summary:
                conversation_id = summary.conversation_id
                print(f"  ✓ Chunk {chunk_id}: trouvé via summary -> conversation_id = {conversation_id}")
            else:
                # Méthode 2: Chercher dans les messages avec même texte (moins fiable)
                message = db.query(Message).filter(
                    Message.content.ilike(f'%{chunk_text_preview[:50]}%')
                ).first()
                
                if message:
                    conversation_id = message.conversation_id
                    print(f"  ✓ Chunk {chunk_id}: trouvé via message -> conversation_id = {conversation_id}")
            
            if conversation_id:
                # Mettre à jour le metadata
                updated_metadata = current_metadata.copy()
                updated_metadata['conversation_id'] = conversation_id
                
                # Déterminer si c'est Gmail ou WhatsApp
                if current_metadata.get('source') == 'gmail':
                    updated_metadata['thread_id'] = conversation_id
                
                # Mettre à jour dans la DB
                update_query = sql_text("""
                    UPDATE embeddings
                    SET metadata = :metadata::jsonb
                    WHERE id = :chunk_id
                """)
                
                db.execute(update_query, {
                    "metadata": json.dumps(updated_metadata),
                    "chunk_id": chunk_id
                })
                
                updated_count += 1
            else:
                print(f"  ✗ Chunk {chunk_id}: impossible de trouver conversation_id, ignoré")
                skipped_count += 1
        
        db.commit()
        
        print(f"\n✅ Migration terminée:")
        print(f"  - Chunks mis à jour: {updated_count}")
        print(f"  - Chunks ignorés: {skipped_count}")
        
        if skipped_count > 0:
            print(f"\n⚠️  {skipped_count} chunks n'ont pas pu être mis à jour automatiquement.")
            print("   Vous devrez peut-être les réimporter ou les mettre à jour manuellement.")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Erreur lors de la migration: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("🔄 Démarrage de la migration des chunks...")
    migrate_chunks()
    print("✅ Migration terminée!")

