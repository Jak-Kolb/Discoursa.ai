import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from cryptography.fernet import Fernet
from ..db import getSession
from ..models import User

router = APIRouter(prefix="/user", tags=["user"])

class UserConfig(BaseModel):
    twitter_id: str
    openai_api_key: str

def get_fernet():
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        # Generate a key if not provided (for dev/demo purposes, ideally should be persistent)
        # In production, this MUST be a persistent env var
        key = Fernet.generate_key().decode()
        print(f"WARNING: ENCRYPTION_KEY not set. Using generated key: {key}")
    return Fernet(key.encode() if isinstance(key, str) else key)

@router.post("/config")
def update_user_config(config: UserConfig, db: Session = Depends(getSession)):
    user = db.query(User).filter(User.id == config.twitter_id).first()
    
    fernet = get_fernet()
    encrypted_key = fernet.encrypt(config.openai_api_key.encode()).decode()
    
    if not user:
        user = User(id=config.twitter_id, encrypted_api_key=encrypted_key)
        db.add(user)
    else:
        user.encrypted_api_key = encrypted_key
    
    db.commit()
    return {"status": "success", "message": "Configuration updated"}
