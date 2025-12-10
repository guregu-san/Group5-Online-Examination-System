import os
from app import app, scheduler
from app.scheduler import set_exam_timers


#----------------------------------------
# launch
#----------------------------------------

# Debug: print all registered routes - for me to see if blueprint routes are registered
print(app.url_map)

if __name__ == "__main__":
    # Necessary guard to avoid duplicate schedulers when running in debug mode
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        scheduler.add_job(
            id="schedule_timers",
            func=set_exam_timers,
            trigger="interval",
            seconds=5, # Less than 1 min for testing
            replace_existing=True
        )

        scheduler.start()
        print("[Scheduler] Started")

    app.run(debug=True, port=5001)
