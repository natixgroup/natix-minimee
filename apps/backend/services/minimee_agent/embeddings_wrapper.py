"""
LangChain embeddings wrapper for Minimee's existing embedding system
Reuses sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
"""
from typing import List
from langchain_core.embeddings import Embeddings
from services.embeddings import generate_embedding


class MinimeeEmbeddings(Embeddings):
    """
    Wrapper around Minimee's existing embedding system for LangChain compatibility
    Reuses the existing sentence-transformers model and generate_embedding function
    """
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of documents
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (each is a list of 384 floats)
        """
        return [generate_embedding(text) for text in texts]
    
    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query string
        
        Args:
            text: Query text to embed
            
        Returns:
            Embedding vector (list of 384 floats)
        """
        return generate_embedding(text)


