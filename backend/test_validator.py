import sys
sys.path.append('.')
import asyncio
from extraction.validator import Validator
from database import get_db

async def main():
    raw_json = {
        "entities": [],
        "tasks": [],
        "ideas": [],
        "decisions": [
            {
                "title": "Use PostgreSQL",
                "status": "Active"
            }
        ],
        "relationships": []
    }
    async with get_db() as db:
        validator = Validator(db, "fake-id")
        cleaned_data = await validator.validate_and_resolve(raw_json)
        print("Cleaned data:", cleaned_data)

if __name__ == "__main__":
    asyncio.run(main())
