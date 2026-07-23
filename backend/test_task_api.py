import sys
sys.path.append('.')
import calendar_service

try:
    task_id = calendar_service.create_google_task("Test task", None)
    print("Task ID:", task_id)
except Exception as e:
    import traceback
    traceback.print_exc()
