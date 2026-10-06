import subprocess
import psutil
from scale import get_dynamic_limits

# Get scaled values dynamically based on available memory
max_tokens, max_history_window, context_len = get_dynamic_limits()

PRIMARY_MODEL = "MythoMax-L2-Kimiko-v2-13B"
FALLBACK_MODEL = "phi-3-mini-4k-instruct"  
MIN_RAM_FOR_13B_GB = 9.0

def get_installed_models():
    """Returns a list of model IDs currently downloaded on the machine."""
    try:
        result = subprocess.run(
            ["lms", "ls"], check=True, text=True, encoding="utf-8", errors="ignore", capture_output=True
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return ""

def ensure_model_downloaded(model_key):
    """Checks if a model is downloaded; if not, triggers an automated download via CLI."""
    installed_output = get_installed_models()
    
    # Check if the model name is found in the local list
    if model_key.lower() not in installed_output.lower():
        print(f"[Download Manager] Model '{model_key}' not found locally. Starting automated download...")
        try:
            # lms get downloads the model (you can append a specific quantization like @q4_k_m if needed)
            subprocess.run(
                ["lms", "get", model_key], 
                check=True, text=True, encoding="utf-8", errors="ignore"
            )
            print(f"[Download Manager] Successfully downloaded: {model_key}")
        except subprocess.CalledProcessError as e:
            print(f"Error: Failed to download model '{model_key}'.")
            return False
    else:
        print(f"[Download Manager] Model '{model_key}' is already available locally.")
    return True

def load_model_preemptive_check():
    mem = psutil.virtual_memory()
    free_ram_gb = mem.available / (1024 ** 3)
    gpu_setting = "0" 

    # Determine which model we intend to use based on RAM headroom
    if free_ram_gb < MIN_RAM_FOR_13B_GB:
        print(f"[Preemptive Check] Low free RAM ({free_ram_gb:.2f}GB). Selecting fallback model.")
        target_model = FALLBACK_MODEL
        target_context = "1024"
    else:
        print(f"[Preemptive Check] Sufficient free RAM ({free_ram_gb:.2f}GB). Selecting primary model.")
        target_model = PRIMARY_MODEL
        target_context = context_len

    # Ensure the target model is downloaded before trying to load it
    is_ready = ensure_model_downloaded(target_model)
    if not is_ready and target_model == PRIMARY_MODEL:
        print("Falling back to lightweight model due to download failure...")
        target_model = FALLBACK_MODEL
        target_context = "1024"
        ensure_model_downloaded(target_model)

    # Load the model into LM Studio
    cmd = ["lms", "load", target_model, "--gpu", gpu_setting, "--context-length", target_context]
    print(f"[Automation] Running command: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True, text=True, encoding="utf-8", errors="ignore", capture_output=True)
        print(f"Successfully loaded model: {target_model}")
        return target_model
    except subprocess.CalledProcessError as e:
        print(f"Error loading model:\n{e.stderr}")
        raise RuntimeError("Model loading failed.")

# Execute the smart download and load logic
active_model = load_model_preemptive_check()

# Initialize your KimikoConfig class using the active model
class KimikoConfig:
    api_url: str = "http://localhost:1234/v1/chat/completions"
    model_name: str = active_model
    save_file: str = "connectai_memory.json"
    short_term_lifetime: int = 2160000  
    promotion_threshold: int = 3
    similarity_threshold: float = 0.75
    temperature: float = 0.8
    max_tokens: int = max_tokens
    max_history_window: int = max_history_window

print(f"Config loaded -> Model: {KimikoConfig.model_name} | Max Tokens: {KimikoConfig.max_tokens}")