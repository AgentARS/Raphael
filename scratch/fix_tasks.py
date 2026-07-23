import re

with open('backend/routers/tasks.py', 'r') as f:
    content = f.read()

# Fix double project_name
content = re.sub(r'project_name=row\["project_name"\],\s*project_name=row\["project_name"\],', r'project_name=row["project_name"],', content)

# Ensure all project_id=row["project_id"], have project_name=row["project_name"], after them
content = re.sub(r'project_id=row\["project_id"\],(?!\s*project_name=)', r'project_id=row["project_id"],\n        project_name=row["project_name"],', content)

# Ensure all SELECT * FROM tasks are replaced with the JOIN query
# Specifically in update_task, update_task_status, delete_task, list_tasks
# But wait, let's just use regex for TaskResponse instantiation.

# Let's fix the specific SELECT queries that were missed.
content = content.replace('cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))',
                          'cursor = await db.execute("""\n            SELECT tasks.*, entities.name as project_name \n            FROM tasks \n            LEFT JOIN entities ON tasks.project_id = entities.id \n            WHERE tasks.id = ?\n        """, (task_id,))')

# Write back
with open('backend/routers/tasks.py', 'w') as f:
    f.write(content)
