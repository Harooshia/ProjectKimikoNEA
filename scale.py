import psutil

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

def get_dynamic_limits():
    """Checks system RAM and GPU VRAM and returns optimal token, history, and context limits."""
    mem = psutil.virtual_memory()
    available_ram_gb = mem.available / (1024 ** 3)
    
    available_vram_gb = 0.0
    if TORCH_AVAILABLE and torch.cuda.is_available():
        free_bytes, _ = torch.cuda.mem_get_info(0)
        available_vram_gb = free_bytes / (1024 ** 3)
        
    total_available = available_vram_gb if available_vram_gb > 0 else available_ram_gb
    print(f"[Hardware Check] RAM: {available_ram_gb:.2f}GB | VRAM: {available_vram_gb:.2f}GB")

    # Scale down settings and context length safely based on available memory
    if total_available < 8.0:
        # Low/Moderate memory (e.g., ~6GB RAM free, 0 VRAM)
        return 150, 8, "1024"   # (max_tokens, max_history_window, context_length)
    else:
        # High memory
        return 500, 25, "4096"