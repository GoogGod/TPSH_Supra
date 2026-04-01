import os

env = os.getenv('DJANGO_ENV', 'development')

if env == 'production':
    from .prod import *
else:
    from .dev import *
    
print(f"Using settings from: {env}.py")