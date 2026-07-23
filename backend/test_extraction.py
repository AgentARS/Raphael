import asyncio
import json
from extraction.validator import Validator
from database import get_db

async def test():
    async with get_db() as db:
        # 1. Setup - let's create "Dr. Rahul Sharma" directly in DB
        await db.execute(
            "INSERT OR IGNORE INTO entities (id, type, name, aliases, confidence, mention_count) VALUES ('test_id_1', 'Person', 'rahul sharma', '[]', 1.0, 1)"
        )
        await db.commit()

        # 2. Mock JSON from LLM
        mock_llm_output = {
            "entities": [
                {"name": "Rahul", "type": "Person", "confidence": 0.9},
                {"name": "Postgres", "type": "Tool", "confidence": 0.8},
                {"name": "Garbage", "type": "Topic", "confidence": 0.2} # should be dropped
            ],
            "tasks": [],
            "ideas": [],
            "relationships": [
                {"source_entity": "Rahul", "source_type": "Person", "target_entity": "Postgres", "target_type": "Tool", "relationship_type": "discussed", "confidence": 0.9},
                {"source_entity": "Rahul", "source_type": "Person", "target_entity": "Postgres", "target_type": "Tool", "relationship_type": "contains", "confidence": 0.9} # invalid ontology, should be dropped
            ]
        }
        
        print("Raw JSON:", json.dumps(mock_llm_output, indent=2))
        
        validator = Validator(db, "fake_entry_id")
        result = await validator.validate_and_resolve(mock_llm_output)
        
        print("\nCleaned Result:", json.dumps(result, indent=2))
        
        # Verify DB changes
        cursor = await db.execute("SELECT name, aliases, mention_count FROM entities WHERE id = 'test_id_1'")
        row = await cursor.fetchone()
        print("\nRahul DB Record:", dict(row))

if __name__ == "__main__":
    asyncio.run(test())
