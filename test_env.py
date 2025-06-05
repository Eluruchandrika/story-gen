import os
from dotenv import dotenv_values

env_vars = dotenv_values(".env")  # load only from .env file, ignore OS env

print("From .env file:", env_vars.get("MONGO_URI"))

# Overwrite environment variables explicitly
for k, v in env_vars.items():
    os.environ[k] = v

print("From os.environ after overwrite:", os.getenv("MONGO_URI"))
