import os

env = os.getenv("DJANGO_ENV", "production").lower()

env = "dev"

if env in {"production", "prod"}:
    from .prod import *
else:
    from .dev import *
    
print(f"Using settings from: {env}.py")
