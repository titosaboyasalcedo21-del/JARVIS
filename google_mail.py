import logging
from google_auth import get_service
import base64
from datetime import datetime

log = logging.getLogger("jarvis.google_mail")

async def get_unread_count():
    import asyncio
    def _fetch():
        service = get_service('gmail', 'v1')
        if not service:
            return {"total": 0, "accounts": {}}
        
        try:
            results = service.users().labels().get(userId='me', id='INBOX').execute()
            unread_count = results.get('messagesUnread', 0)
            return {"total": unread_count, "accounts": {"Gmail": unread_count}}
        except Exception as e:
            log.error(f"Error getting Gmail unread count: {e}")
            return {"total": 0, "accounts": {}}
    return await asyncio.to_thread(_fetch)
async def get_recent_messages(count=10):
    service = get_service('gmail', 'v1')
    if not service:
        return []
    
    try:
        results = service.users().messages().list(userId='me', maxResults=count, labelIds=['INBOX']).execute()
        messages = results.get('messages', [])
        
        full_messages = []
        for msg in messages:
            m = service.users().messages().get(userId='me', id=msg['id']).execute()
            payload = m.get('payload', {})
            headers = payload.get('headers', [])
            
            subject = sender = date = ""
            for h in headers:
                if h['name'] == 'Subject': subject = h['value']
                if h['name'] == 'From': sender = h['value']
                if h['name'] == 'Date': date = h['value']
            
            snippet = m.get('snippet', "")
            read = 'UNREAD' not in m.get('labelIds', [])
            
            full_messages.append({
                "id": msg['id'],
                "sender": sender,
                "subject": subject,
                "date": date,
                "read": read,
                "preview": snippet
            })
        return full_messages
    except Exception as e:
        log.error(f"Error getting recent Gmail messages: {e}")
        return []

async def read_message(msg_id):
    service = get_service('gmail', 'v1')
    if not service:
        return None
    
    try:
        m = service.users().messages().get(userId='me', id=msg_id).execute()
        payload = m.get('payload', {})
        headers = payload.get('headers', [])
        
        subject = sender = date = ""
        for h in headers:
            if h['name'] == 'Subject': subject = h['value']
            if h['name'] == 'From': sender = h['value']
            if h['name'] == 'Date': date = h['value']
            
        content = m.get('snippet', "") # Simplifying content for now
        
        return {
            "sender": sender,
            "subject": subject,
            "date": date,
            "content": content
        }
    except Exception as e:
        log.error(f"Error reading Gmail message: {e}")
        return None
