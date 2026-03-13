
from javs.config.loader import load_config

config = load_config()
print(f"Move subtitles: {config.sort.move_subtitles}")
