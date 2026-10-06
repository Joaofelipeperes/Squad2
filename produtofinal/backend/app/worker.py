"""Processo de tarefas agendadas (separado da API para não duplicar jobs com vários workers web).

    python -m app.worker
"""
import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import app.integrations.ai  # noqa: F401
from app.core.config import get_settings
from app.modules import load_modules

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("worker")


def main() -> None:
    s = get_settings()
    sched = BlockingScheduler(timezone=s.timezone)
    for m in load_modules():
        for job in m.jobs:
            sched.add_job(job.func, CronTrigger.from_crontab(job.cron, timezone=s.timezone),
                          id=f"{m.name}.{job.id}", max_instances=1, coalesce=True,
                          misfire_grace_time=3600)
            log.info("Job agendado: %s.%s (%s)", m.name, job.id, job.cron)
    sched.start()


if __name__ == "__main__":
    main()
