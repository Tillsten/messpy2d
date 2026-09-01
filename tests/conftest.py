from loguru import logger


def pytest_sessionfinish(session, exitstatus):
    """Detach loguru sinks before interpreter shutdown.

    Instrument mocks register atexit save_state() calls that log through
    loguru. By the time atexit runs, pytest has already closed the captured
    stdout/stderr streams, so those log writes raise "I/O operation on
    closed file" and pytest-qt reports it as a non-zero exit. Removing the
    sinks here (while streams are still open) turns later log calls into
    no-ops instead of failures.
    """
    logger.remove()
