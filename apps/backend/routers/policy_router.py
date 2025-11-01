"""
Policy management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from db.database import get_db
from models import Policy
from schemas import PolicyCreate, PolicyUpdate, PolicyResponse

router = APIRouter()


@router.get("/policy", response_model=List[PolicyResponse])
async def list_policies(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """List all policies"""
    query = db.query(Policy)
    if user_id:
        query = query.filter(Policy.user_id == user_id)
    return query.all()


@router.post("/policy", response_model=PolicyResponse)
async def create_policy(
    policy_data: PolicyCreate,
    db: Session = Depends(get_db)
):
    """Create new policy"""
    policy = Policy(**policy_data.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.get("/policy/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: int,
    db: Session = Depends(get_db)
):
    """Get policy by ID"""
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.put("/policy/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: int,
    policy_data: PolicyUpdate,
    db: Session = Depends(get_db)
):
    """Update policy"""
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    update_data = policy_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(policy, key, value)
    
    db.commit()
    db.refresh(policy)
    return policy


@router.delete("/policy/{policy_id}")
async def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db)
):
    """Delete policy"""
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    db.delete(policy)
    db.commit()
    return {"message": "Policy deleted"}

