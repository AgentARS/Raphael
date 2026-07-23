import os
import datetime
import threading
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks'
]

_creds = None
_thread_local = threading.local()

def get_credentials():
    global _creds
    
    if _creds and _creds.valid:
        return _creds

    base_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(base_dir, 'token.json')
    creds_path = os.path.join(base_dir, 'credentials.json')

    if os.path.exists(token_path):
        _creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
    if not _creds or not _creds.valid:
        if _creds and _creds.expired and _creds.refresh_token:
            try:
                _creds.refresh(Request())
            except RefreshError:
                if os.path.exists(token_path):
                    os.remove(token_path)
                if not os.path.exists(creds_path):
                    raise FileNotFoundError(f"Missing {creds_path}. Please download it from Google Cloud Console.")
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                _creds = flow.run_local_server(port=0)
        else:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(f"Missing {creds_path}. Please download it from Google Cloud Console.")
            
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            _creds = flow.run_local_server(port=0)
            
        with open(token_path, 'w') as token:
            token.write(_creds.to_json())

    return _creds

def get_calendar_service():
    if not hasattr(_thread_local, 'calendar_service'):
        _thread_local.calendar_service = build('calendar', 'v3', credentials=get_credentials())
    return _thread_local.calendar_service

def get_tasks_service():
    if not hasattr(_thread_local, 'tasks_service'):
        _thread_local.tasks_service = build('tasks', 'v1', credentials=get_credentials())
    return _thread_local.tasks_service

def get_upcoming_events(max_results=10):
    service = get_calendar_service()
    now_dt = datetime.datetime.utcnow()
    now = now_dt.isoformat() + 'Z'
    # Bound to next 14 days so we don't just fetch 10 years of birthdays
    time_max = (now_dt + datetime.timedelta(days=14)).isoformat() + 'Z'
    
    events_result = service.events().list(
        calendarId='primary', 
        timeMin=now,
        timeMax=time_max,
        maxResults=max_results, 
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    return events

def get_user_timezone():
    try:
        service = get_calendar_service()
        calendar = service.calendars().get(calendarId='primary').execute()
        return calendar.get('timeZone', 'UTC')
    except Exception:
        return 'UTC'

def create_event(summary: str, start_time: str, end_time: str, description: str = "", recurrence: list[str] = None, color_id: str = None):
    service = get_calendar_service()
    user_tz = get_user_timezone()
    
    # Strip Z if present, as we use the calendar's timezone
    if start_time.endswith('Z'):
        start_time = start_time[:-1]
    if end_time.endswith('Z'):
        end_time = end_time[:-1]
        
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': user_tz,
        },
        'end': {
            'dateTime': end_time,
            'timeZone': user_tz,
        },
    }
    
    if recurrence:
        event['recurrence'] = recurrence
    if color_id:
        event['colorId'] = color_id
        
    event = service.events().insert(calendarId='primary', body=event).execute()
    return event

def update_event(event_id: str, summary: str = None, start_time: str = None, end_time: str = None, description: str = None, recurrence: list[str] = None, color_id: str = None):
    service = get_calendar_service()
    user_tz = get_user_timezone()
    
    # First, fetch the existing event
    event = service.events().get(calendarId='primary', eventId=event_id).execute()
    
    if summary is not None:
        event['summary'] = summary
    if description is not None:
        event['description'] = description
        
    if start_time is not None:
        if start_time.endswith('Z'):
            start_time = start_time[:-1]
        event['start'] = {'dateTime': start_time, 'timeZone': user_tz}
        
    if end_time is not None:
        if end_time.endswith('Z'):
            end_time = end_time[:-1]
        event['end'] = {'dateTime': end_time, 'timeZone': user_tz}
        
    if recurrence is not None:
        event['recurrence'] = recurrence
    if color_id is not None:
        event['colorId'] = color_id
        
    updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
    return updated_event

def delete_event(event_id: str):
    service = get_calendar_service()
    service.events().delete(calendarId='primary', eventId=event_id).execute()
    return True

# ----------------- Tasks API Helpers -----------------

def create_google_task(title: str, due_date: str = None) -> str:
    try:
        service = get_tasks_service()
        task = {
            'title': title
        }
        if due_date:
            # Tasks API due dates must be RFC 3339 timestamps (e.g. 2026-07-11T00:00:00.000Z)
            # Ensure it ends with Z
            if len(due_date) == 10:  # YYYY-MM-DD
                due_date += "T00:00:00.000Z"
            task['due'] = due_date
            
        result = service.tasks().insert(tasklist='@default', body=task).execute()
        return result.get('id')
    except Exception as e:
        print(f"Error creating google task: {e}")
        return None

def update_google_task(task_id: str, title: str = None, status: str = None, due_date: str = None) -> bool:
    try:
        service = get_tasks_service()
        task = service.tasks().get(tasklist='@default', task=task_id).execute()
        
        if title is not None:
            task['title'] = title
        if status is not None:
            # Google tasks status is 'needsAction' or 'completed'
            task['status'] = 'completed' if status == 'done' else 'needsAction'
        if due_date is not None:
            if due_date == "":
                task.pop('due', None)
            else:
                if len(str(due_date)) == 10:
                    task['due'] = str(due_date) + "T00:00:00.000Z"
                else:
                    task['due'] = str(due_date)
            
        service.tasks().update(tasklist='@default', task=task_id, body=task).execute()
        return True
    except Exception as e:
        print(f"Error updating google task: {e}")
        return False

def delete_google_task(task_id: str) -> bool:
    try:
        service = get_tasks_service()
        service.tasks().delete(tasklist='@default', task=task_id).execute()
        return True
    except Exception as e:
        print(f"Error deleting google task: {e}")
        return False

def get_all_google_tasks() -> dict:
    """Returns a dictionary of google_task_id -> task_metadata"""
    try:
        service = get_tasks_service()
        tasks = {}
        page_token = None
        while True:
            # showHidden and showDeleted ensures we get completed and deleted tasks
            results = service.tasks().list(
                tasklist='@default', 
                maxResults=100, 
                pageToken=page_token, 
                showCompleted=True, 
                showHidden=True, 
                showDeleted=True
            ).execute()
            
            for task in results.get('items', []):
                tasks[task['id']] = task
                
            page_token = results.get('nextPageToken')
            if not page_token:
                break
        return tasks
    except Exception as e:
        print(f"Error fetching google tasks: {e}")
        return None
