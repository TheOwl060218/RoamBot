"""Invitation URLs are bearer credentials and must not appear in access logs."""

import logging
import re

INVITE_PATH = re.compile(r"(/api/v1/public/plans/|/join/)[^/\s?]+")


class PlanAccessFilter(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            args = list(record.args)
            if isinstance(args[2], str) and INVITE_PATH.search(args[2]):
                args[2] = INVITE_PATH.sub(r"\1[redacted]", args[2]).split("?")[0]
                record.args = tuple(args)
        return True


def protect_plan_access_logs():
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, PlanAccessFilter) for f in logger.filters):
        logger.addFilter(PlanAccessFilter())
