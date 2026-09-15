import os
import psutil
import logging
import asyncio
import ollama
from typing import Optional, AsyncGenerator

logger = logging.getLogger("llm_manager")
logger.setLevel(logging.INFO)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MAX_SWAP_BYTES = 9 * 1024 * 1024 * 1024  # 9GB

HEAVY_MODEL = os.getenv("HEAVY_MODEL", "qwen3:8b")
LIGHT_MODEL = os.getenv("LIGHT_MODEL", "gemma4:e4b")

model_lock = asyncio.Lock()
currently_loaded_model = None

class SystemMemoryOverloadError(Exception):
    """Raised when the system memory (swap) exceeds safe limits."""
    pass

async def unload_model(model_name: str):
    """Forcefully unloads a specific model."""
    client = ollama.AsyncClient(host=OLLAMA_BASE_URL)
    try:
        logger.info(f"Unloading model {model_name} from memory...")
        await client.generate(model=model_name, prompt="", keep_alive=0)
    except Exception as e:
        logger.error(f"Failed to unload model {model_name}: {e}")

async def unload_all_models():
    """Forcefully unloads all models currently loaded in Ollama to free up memory."""
    global currently_loaded_model
    client = ollama.AsyncClient(host=OLLAMA_BASE_URL)
    try:
        ps = await client.ps()
        models = ps.get('models', [])
        for model_info in models:
            model_name = model_info.get('name')
            if model_name:
                await unload_model(model_name)
        currently_loaded_model = None
    except Exception as e:
        logger.error(f"Failed to unload all models: {e}")

async def check_memory_safety():
    """
    Checks if swap memory is above the threshold.
    If so, unloads models and raises SystemMemoryOverloadError.
    """
    try:
        swap = psutil.swap_memory()
        if swap.used > MAX_SWAP_BYTES:
            logger.warning(f"Swap memory exceeded limit! Used: {swap.used / (1024**3):.2f} GB")
            await unload_all_models()
            raise SystemMemoryOverloadError(f"System swap memory overloaded ({swap.used / (1024**3):.2f} GB used).")
    except AttributeError:
        pass

async def ensure_only_model_loaded(target_model: str):
    """Queries Ollama for loaded models and unloads anything that isn't the target model."""
    global currently_loaded_model
    client = ollama.AsyncClient(host=OLLAMA_BASE_URL)
    try:
        ps = await client.ps()
        models = ps.get('models', [])
        for model_info in models:
            model_name = model_info.get('name')
            if model_name and model_name != target_model:
                await unload_model(model_name)
        currently_loaded_model = target_model
    except Exception as e:
        logger.error(f"Failed to query or unload models: {e}")

async def generate_chat(
    model: str, 
    messages: list, 
    format: Optional[str] = None, 
    options: Optional[dict] = None, 
    stream: bool = False
):
    """
    Wrapper around ollama.AsyncClient().chat() that enforces memory safety and model locking.
    """
    await check_memory_safety()
    
    kwargs = {
        "model": model,
        "messages": messages,
        "stream": stream
    }
    if format is not None:
        kwargs["format"] = format
    if options is not None:
        kwargs["options"] = options

    if stream:
        async def stream_generator():
            async with model_lock:
                await ensure_only_model_loaded(model)
                client = ollama.AsyncClient(host=OLLAMA_BASE_URL)
                response_gen = await client.chat(**kwargs)
                async for chunk in response_gen:
                    yield chunk
        return stream_generator()
    else:
        async with model_lock:
            await ensure_only_model_loaded(model)
            client = ollama.AsyncClient(host=OLLAMA_BASE_URL)
            return await client.chat(**kwargs)
