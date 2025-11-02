"""
Action Logger Service - Log toutes les actions du système avec timing et détails
"""
import time
import uuid
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime
from models import ActionLog
from functools import wraps


def generate_request_id() -> str:
    """Génère un ID unique pour une requête"""
    return str(uuid.uuid4())


def log_action(
    db: Session,
    action_type: str,
    duration_ms: Optional[float] = None,
    model: Optional[str] = None,
    input_data: Optional[Dict[str, Any]] = None,
    output_data: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    message_id: Optional[int] = None,
    conversation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    user_id: Optional[int] = None,
    source: Optional[str] = None,
    status: str = "success",
    error_message: Optional[str] = None
) -> ActionLog:
    """
    Log une action dans la table action_logs
    
    Args:
        action_type: Type d'action (message_arrived, vectorization, semantic_search, etc.)
        duration_ms: Durée en millisecondes
        model: Modèle utilisé (embedding model, LLM model, etc.)
        input_data: Données d'entrée (message, query, prompt, etc.)
        output_data: Données de sortie (embedding, results, response, etc.)
        metadata: Métadonnées supplémentaires
        message_id: ID du message associé
        conversation_id: ID de la conversation
        request_id: ID de la requête (pour tracer un flux complet)
        user_id: ID de l'utilisateur
        source: Source du message ('whatsapp', 'gmail', etc.)
        status: Statut ('success', 'error', 'pending')
        error_message: Message d'erreur si status=error
    """
    action_log = ActionLog(
        action_type=action_type,
        duration_ms=duration_ms,
        model=model,
        input_data=input_data,
        output_data=output_data,
        meta_data=metadata,  # Changed from metadata to meta_data to match model
        message_id=message_id,
        conversation_id=conversation_id,
        request_id=request_id,
        user_id=user_id,
        source=source,
        status=status,
        error_message=error_message,
        timestamp=datetime.utcnow()
    )
    db.add(action_log)
    db.commit()
    db.refresh(action_log)
    return action_log


@contextmanager
def log_action_context(
    db: Session,
    action_type: str,
    model: Optional[str] = None,
    input_data: Optional[Dict[str, Any]] = None,
    message_id: Optional[int] = None,
    conversation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    user_id: Optional[int] = None,
    source: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Context manager pour logger une action avec mesure automatique du temps
    
    Usage:
        with log_action_context(db, "vectorization", model="sentence-transformers/all-MiniLM-L6-v2", input_data={"text": "..."}, request_id=req_id) as log:
            # Code à mesurer
            result = do_something()
            log.set_output({"embedding_dim": len(result)})
    """
    start_time = time.time()
    error_occurred = False
    error_message = None
    log_context = LogContext()
    
    try:
        yield log_context
        status = "success"
    except Exception as e:
        error_occurred = True
        error_message = str(e)
        status = "error"
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000
        # Merge metadata update if any
        final_metadata = metadata or {}
        if log_context.metadata_update:
            final_metadata.update(log_context.metadata_update)
        
        log_action(
            db=db,
            action_type=action_type,
            duration_ms=duration_ms,
            model=model,
            input_data=input_data,
            output_data=log_context.output_data,
            metadata=final_metadata if final_metadata else None,
            message_id=message_id,
            conversation_id=conversation_id,
            request_id=request_id,
            user_id=user_id,
            source=source,
            status=status,
            error_message=error_message
        )


class LogContext:
    """Helper class pour mettre à jour les données de sortie dans le context manager"""
    def __init__(self):
        self.output_data: Optional[Dict[str, Any]] = None
        self.metadata_update: Optional[Dict[str, Any]] = None
    
    def set_output(self, output_data: Dict[str, Any]):
        """Définit les données de sortie"""
        self.output_data = output_data
    
    def update_metadata(self, metadata: Dict[str, Any]):
        """Met à jour les métadonnées"""
        self.metadata_update = metadata


def log_action_decorator(action_type: str, model_param: Optional[str] = None):
    """
    Décorateur pour logger une action avec mesure automatique du temps
    
    Usage:
        @log_action_decorator("vectorization", model_param="embedding_model")
        def generate_embedding(text: str, embedding_model: str = "all-MiniLM-L6-v2", db: Session = None):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extraire db du kwargs ou args
            db = kwargs.get('db') or (args[-1] if args and isinstance(args[-1], Session) else None)
            if not db:
                # Si pas de db, exécuter sans logging
                return func(*args, **kwargs)
            
            # Extraire le modèle si spécifié
            model = None
            if model_param:
                model = kwargs.get(model_param) or getattr(kwargs.get('self'), model_param, None)
            
            # Générer request_id si disponible
            request_id = kwargs.get('request_id')
            
            # Préparer input_data
            input_data = {}
            if args:
                # Prendre le premier arg comme input si c'est une string
                if isinstance(args[0], str):
                    input_data["text"] = args[0][:500]  # Limiter la taille
            
            start_time = time.time()
            error_occurred = False
            error_message = None
            result = None
            
            try:
                result = func(*args, **kwargs)
                status = "success"
            except Exception as e:
                error_occurred = True
                error_message = str(e)
                status = "error"
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                # Préparer output_data
                output_data = None
                if result is not None:
                    if isinstance(result, (list, tuple)):
                        output_data = {"type": type(result).__name__, "length": len(result)}
                    elif isinstance(result, dict):
                        output_data = result
                    elif isinstance(result, str):
                        output_data = {"text": result[:500]}  # Limiter la taille
                    else:
                        output_data = {"type": type(result).__name__}
                
                log_action(
                    db=db,
                    action_type=action_type,
                    duration_ms=duration_ms,
                    model=model,
                    input_data=input_data if input_data else None,
                    output_data=output_data,
                    message_id=kwargs.get('message_id'),
                    conversation_id=kwargs.get('conversation_id'),
                    request_id=request_id,
                    user_id=kwargs.get('user_id'),
                    source=kwargs.get('source'),
                    status=status,
                    error_message=error_message
                )
            
            return result
        return wrapper
    return decorator

