#!/usr/bin/env python3
"""Check RAG logs in database"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db.database import SessionLocal
from models import ActionLog, Log
from sqlalchemy import desc
from datetime import datetime, timedelta

db = SessionLocal()
try:
    print("=" * 80)
    print("CHECKING ACTION_LOGS (semantic_search)")
    print("=" * 80)
    
    # Check action_logs for semantic_search
    action_logs = db.query(ActionLog).filter(
        ActionLog.action_type == 'semantic_search'
    ).order_by(desc(ActionLog.timestamp)).limit(10).all()
    
    print(f"Found {len(action_logs)} semantic_search logs")
    print()
    
    if action_logs:
        for log in action_logs:
            print(f"Timestamp: {log.timestamp}")
            print(f"  Action: {log.action_type}")
            print(f"  Model: {log.model}")
            print(f"  Status: {log.status}")
            print(f"  User ID: {log.user_id}")
            print(f"  Conversation ID: {log.conversation_id}")
            print(f"  Request ID: {log.request_id}")
            if log.input_data:
                print(f"  Input: {log.input_data}")
            if log.output_data:
                print(f"  Output: {log.output_data}")
            print()
    else:
        print("NO SEMANTIC_SEARCH LOGS FOUND!")
        print()
    
    print("=" * 80)
    print("CHECKING LOGS (rag_llamaindex, minimee_router)")
    print("=" * 80)
    
    # Check logs for RAG
    logs = db.query(Log).filter(
        Log.service.in_(['rag_llamaindex', 'minimee_router'])
    ).order_by(desc(Log.timestamp)).limit(10).all()
    
    print(f"Found {len(logs)} RAG-related logs")
    print()
    
    if logs:
        for log in logs:
            print(f"Timestamp: {log.timestamp}")
            print(f"  Level: {log.level}")
            print(f"  Service: {log.service}")
            print(f"  Message: {log.message[:200]}")
            if log.meta_data:
                print(f"  Metadata: {log.meta_data}")
            print()
    else:
        print("NO RAG-RELATED LOGS FOUND!")
        print()
    
    print("=" * 80)
    print("RECENT ACTION_LOGS (all types)")
    print("=" * 80)
    
    # Check recent action_logs of any type
    recent_logs = db.query(ActionLog).order_by(
        desc(ActionLog.timestamp)
    ).limit(10).all()
    
    print(f"Found {len(recent_logs)} recent action logs")
    print()
    
    for log in recent_logs:
        print(f"  {log.timestamp}: {log.action_type} (status={log.status}, user_id={log.user_id})")
    
    print()
    print("=" * 80)
    print("RECENT LOGS (all services)")
    print("=" * 80)
    
    # Check recent logs of any service
    recent_regular_logs = db.query(Log).order_by(
        desc(Log.timestamp)
    ).limit(10).all()
    
    print(f"Found {len(recent_regular_logs)} recent logs")
    print()
    
    for log in recent_regular_logs:
        print(f"  {log.timestamp}: [{log.level}] {log.service} - {log.message[:80]}")
    
finally:
    db.close()






