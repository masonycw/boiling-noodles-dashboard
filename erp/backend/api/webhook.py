from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from erp.backend.db.session import get_db
from erp.backend.db.models import LinePendingGroup
from erp.backend.services.line_service import verify_line_signature, get_setting

router = APIRouter(prefix="/webhook", tags=["webhook"])

@router.post("/line")
async def line_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")
    
    # Verify signature
    secret = get_setting(db, "line_channel_secret")
    if secret and not verify_line_signature(body, signature, secret):
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    try:
        data = json.loads(body)
        events = data.get("events", [])
        
        for event in events:
            event_type = event.get("type")
            source = event.get("source", {})
            
            if event_type == "join" and source.get("type") == "group":
                group_id = source.get("groupId")
                if group_id:
                    # Save to pending groups for admin to match
                    existing = db.query(LinePendingGroup).filter(
                        LinePendingGroup.group_id == group_id
                    ).first()
                    if not existing:
                        pending = LinePendingGroup(group_id=group_id)
                        db.add(pending)
                        db.commit()
    except Exception as e:
        print(f"Webhook error: {e}")
    
    return {"status": "ok"}
