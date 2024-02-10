import os
from invoke import task

@task
def dev(ctx):
    ctx.run(
        "flask --app app.web run --debug --port 2345",
        pty=os.name != "nt",
        env={"APP_ENV": "development"},
    )