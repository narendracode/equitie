from api.celery_app import app


@app.task
def example_task(x: int, y: int) -> int:
    return x + y
