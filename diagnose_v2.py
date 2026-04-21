
import sys
import traceback

print("Starting diagnostics...")

def check(name, task):
    print(f"Checking {name}...", end=" ", flush=True)
    try:
        task()
        print("OK")
    except Exception:
        print("FAIL")
        traceback.print_exc()

def import_extensions(): import extensions
def import_models(): import models
def import_utils(): import utils
def import_auth(): import routes.auth
def import_admin(): import routes.admin
def import_api(): import routes.api
def import_chat(): import routes.chat
def import_planner(): import routes.planner
def import_app(): import app

check("extensions", import_extensions)
check("models", import_models)
check("utils", import_utils)
check("routes.auth", import_auth)
check("routes.admin", import_admin)
check("routes.api", import_api)
check("routes.chat", import_chat)
check("routes.planner", import_planner)
check("app", import_app)
