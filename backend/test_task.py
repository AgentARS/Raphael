import asyncio
import calendar_service

async def main():
    print(calendar_service.create_google_task("Test task", None))

asyncio.run(main())
