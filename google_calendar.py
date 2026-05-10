import logging
from google_auth import get_service
from datetime import datetime, timezone

log = logging.getLogger("jarvis.google_calendar")

async def get_todays_events():
    import asyncio
    def _fetch():
        service = get_service('calendar', 'v3')
        if not service:
            return []
        
        try:
            now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            # End of today
            end_of_day = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59).isoformat().replace('+00:00', 'Z')
            
            events_result = service.events().list(calendarId='primary', timeMin=now, timeMax=end_of_day,
                                                  singleEvents=True, orderBy='startTime').execute()
            events = events_result.get('items', [])
            
            formatted_events = []
            for e in events:
                start = e['start'].get('dateTime', e['start'].get('date'))
                all_day = 'date' in e['start']
                
                # Parse start time for display
                if all_day:
                    time_str = "ALL_DAY"
                else:
                    dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    time_str = dt.strftime("%-I:%M %p")
                
                formatted_events.append({
                    "calendar": "Primary",
                    "title": e.get('summary', '(No title)'),
                    "start": time_str,
                    "all_day": all_day,
                    "start_dt": datetime.fromisoformat(start.replace('Z', '+00:00')) if not all_day else None
                })
            return formatted_events
        except Exception as e:
            log.error(f"Error getting Google Calendar events: {e}")
            return []
            
    return await asyncio.to_thread(_fetch)
