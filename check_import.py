
try:
    import app
    print(f"Has _publish_cell: {hasattr(app, '_publish_cell')}")
except Exception as e:
    print(f"Error: {e}")
