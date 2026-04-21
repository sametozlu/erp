
import sys
import os

print("Diagnostic: checking modules...")

try:
    print("Importing extensions...")
    import extensions
    print("OK.")
except Exception as e:
    print(f"FAIL extensions: {e}")

try:
    print("Importing models...")
    import models
    print("OK.")
except Exception as e:
    print(f"FAIL models: {e}")

try:
    print("Importing utils...")
    import utils
    print("OK.")
except Exception as e:
    print(f"FAIL utils: {e}")

try:
    print("Importing routes.auth...")
    from routes import auth
    print("OK.")
except Exception as e:
    print(f"FAIL routes.auth: {e}")

try:
    print("Importing routes.admin...")
    from routes import admin
    print("OK.")
except Exception as e:
    print(f"FAIL routes.admin: {e}")

try:
    print("Importing routes.api...")
    from routes import api
    print("OK.")
except Exception as e:
    print(f"FAIL routes.api: {e}")

try:
    print("Importing routes.chat...")
    from routes import chat
    print("OK.")
except Exception as e:
    print(f"FAIL routes.chat: {e}")

try:
    print("Importing routes.planner...")
    from routes import planner
    print("OK.")
except Exception as e:
    print(f"FAIL routes.planner: {e}")

try:
    print("Importing app...")
    import app
    print("OK.")
except Exception as e:
    print(f"FAIL app: {e}")

print("Diagnostic complete.")
