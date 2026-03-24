import httpx
import hmac
import hashlib
import base64
from sqlalchemy.orm import Session
from erp.backend.db.models import SystemSetting

def get_setting(db: Session, key: str) -> str:
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    return setting.value if setting and setting.value else ""

def verify_line_signature(body: bytes, signature: str, secret: str) -> bool:
    hash = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest()
    expected = base64.b64encode(hash).decode('utf-8')
    return hmac.compare_digest(expected, signature)

async def send_line_message(group_id: str, message: str, access_token: str) -> bool:
    if not access_token or not group_id:
        return False
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    body = {
        "to": group_id,
        "messages": [{"type": "text", "text": message}]
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=body, headers=headers)
            return response.status_code == 200
    except Exception as e:
        print(f"LINE send error: {e}")
        return False
