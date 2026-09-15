import asyncio
import datetime
import psutil
import logging
from database import get_db
from .tasks import TASK_REGISTRY

logger = logging.getLogger("autonomous_scheduler")
logger.setLevel(logging.INFO)

class AutonomousScheduler:
    def __init__(self):
        self.is_running = False
        self.current_task = None
        self._task_handle = None
        
    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task_handle = asyncio.create_task(self._loop())
        logger.info("Autonomous scheduler started.")
        
    async def stop(self):
        self.is_running = False
        if self._task_handle:
            self._task_handle.cancel()
            try:
                await self._task_handle
            except asyncio.CancelledError:
                pass
        logger.info("Autonomous scheduler stopped.")

    async def _get_settings(self, db):
        cursor = await db.execute("SELECT key, value FROM autonomous_settings")
        rows = await cursor.fetchall()
        return {r['key']: r['value'] for r in rows}

    async def _loop(self):
        while self.is_running:
            try:
                async with get_db() as db:
                    settings = await self._get_settings(db)
                    mode = settings.get('mode', 'manual')
                    
                    if mode != 'autonomous':
                        await asyncio.sleep(10)
                        continue
                        
                    # Check system limits
                    max_cpu = float(settings.get('max_cpu_percent', '80.0'))
                    max_ram = float(settings.get('max_ram_percent', '85.0'))
                    wake_interval = int(settings.get('wake_interval_seconds', '3600'))
                    max_runtime = int(settings.get('max_runtime_per_cycle_seconds', '300'))
                    
                    cpu_percent = psutil.cpu_percent(interval=None)
                    ram_percent = psutil.virtual_memory().percent
                    
                    if cpu_percent > max_cpu or ram_percent > max_ram:
                        logger.warning(f"System load too high (CPU: {cpu_percent}%, RAM: {ram_percent}%). Pausing autonomous mode.")
                        await asyncio.sleep(60)
                        continue
                        
                    from llm_manager import check_memory_safety, SystemMemoryOverloadError
                    try:
                        await check_memory_safety()
                    except SystemMemoryOverloadError as e:
                        logger.warning(f"Pausing autonomous mode: {e}")
                        await asyncio.sleep(60)
                        continue
                        
                    # Get eligible tasks
                    cursor = await db.execute("""
                        SELECT id, name, priority, estimated_cost_ms 
                        FROM autonomous_tasks 
                        WHERE enabled = 1 AND next_eligible_run <= CURRENT_TIMESTAMP
                        ORDER BY priority DESC, next_eligible_run ASC
                    """)
                    tasks = await cursor.fetchall()
                    
                    if not tasks:
                        await asyncio.sleep(10) # Quick poll for "run now" updates
                        continue
                        
                    cycle_start_time = datetime.datetime.now()
                    
                    for task in tasks:
                        # Check if we exceeded cycle budget
                        elapsed = (datetime.datetime.now() - cycle_start_time).total_seconds()
                        if elapsed > max_runtime:
                            logger.info("Cycle time budget exceeded. Yielding.")
                            break
                            
                        task_func = TASK_REGISTRY.get(task['name'])
                        if not task_func:
                            logger.error(f"Task {task['name']} not found in registry.")
                            continue
                            
                        self.current_task = task['name']
                        try:
                            logger.info(f"Running autonomous task: {task['name']}")
                            await task_func(db)
                            
                            # Update last run and next run (default to +1 hour)
                            next_run = (datetime.datetime.utcnow() + datetime.timedelta(seconds=wake_interval)).strftime("%Y-%m-%d %H:%M:%S")
                            await db.execute("""
                                UPDATE autonomous_tasks 
                                SET last_run = CURRENT_TIMESTAMP, next_eligible_run = ?
                                WHERE id = ?
                            """, (next_run, task['id']))
                            await db.commit()
                        except Exception as e:
                            logger.error(f"Error in task {task['name']}: {e}")
                            # basic exponential backoff could be implemented here
                        finally:
                            self.current_task = None
                            
                # Sleep before next cycle
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(60)

scheduler = AutonomousScheduler()
