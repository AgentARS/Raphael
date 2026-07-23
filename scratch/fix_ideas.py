import re

with open('backend/routers/ideas.py', 'r') as f:
    content = f.read()

# Replace SELECT * FROM ideas with JOINs
content = content.replace(
    'cursor = await db.execute(\n                "SELECT * FROM ideas WHERE project_id = ? ORDER BY created_at DESC", \n                (project_id,)\n            )',
    'cursor = await db.execute("""\n                SELECT ideas.*, entities.name as project_name \n                FROM ideas \n                LEFT JOIN entities ON ideas.project_id = entities.id \n                WHERE ideas.project_id = ? \n                ORDER BY ideas.created_at DESC\n            """, (project_id,))'
)

content = content.replace(
    'cursor = await db.execute("SELECT * FROM ideas ORDER BY created_at DESC")',
    'cursor = await db.execute("""\n                SELECT ideas.*, entities.name as project_name \n                FROM ideas \n                LEFT JOIN entities ON ideas.project_id = entities.id \n                ORDER BY ideas.created_at DESC\n            """)'
)

content = content.replace(
    'cursor = await db.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,))',
    'cursor = await db.execute("""\n            SELECT ideas.*, entities.name as project_name \n            FROM ideas \n            LEFT JOIN entities ON ideas.project_id = entities.id \n            WHERE ideas.id = ?\n        """, (idea_id,))'
)

# Replace IdeaResponse instantiations to include project_name
content = re.sub(
    r'project_id=row\["project_id"\],',
    r'project_id=row["project_id"],\n            project_name=row["project_name"],',
    content
)

with open('backend/routers/ideas.py', 'w') as f:
    f.write(content)
