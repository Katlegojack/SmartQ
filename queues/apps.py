from django.apps import AppConfig


class QueuesConfig(AppConfig):
    name = "queues"

    def ready(self):
        # QueueEvent is the append-only operational boundary shared by every
        # check-in/call/complete workflow. Forecasting observations subscribe to
        # that boundary so customer, Reception and Counter paths cannot drift.
        from . import signals  # noqa: F401
