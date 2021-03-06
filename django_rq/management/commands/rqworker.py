import logging
from optparse import make_option

from django.core.management.base import BaseCommand
from django.utils.log import dictConfig

from redis.exceptions import ConnectionError

from django_rq.queues import get_queues

from rq import use_connection
import importlib

# Setup logging for RQWorker if not already configured
logger = logging.getLogger('rq.worker')
if not logger.handlers:
    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,

        "formatters": {
            "rq_console": {
                "format": "%(asctime)s %(message)s",
                "datefmt": "%H:%M:%S",
            },
        },

        "handlers": {
            "rq_console": {
                "level": "DEBUG",
                #"class": "logging.StreamHandler",
                "class": "rq.utils.ColorizingStreamHandler",
                "formatter": "rq_console",
                "exclude": ["%(asctime)s"],
            },
        },

        "worker": {
            "handlers": ["rq_console"],
            "level": "DEBUG"
        }
    })

    
# Copied from rq.utils
def import_attribute(name):
    """Return an attribute from a dotted path name (e.g. "path.to.func")."""
    module_name, attribute = name.rsplit('.', 1)
    module = importlib.import_module(module_name)
    return getattr(module, attribute)


class Command(BaseCommand):
    """
    Runs RQ workers on specified queues. Note that all queues passed into a
    single rqworker command must share the same connection.

    Example usage:
    python manage.py rqworker high medium low
    """
    option_list = BaseCommand.option_list + (
        make_option(
            '--burst',
            action='store_true',
            dest='burst',
            default=False,
            help='Run worker in burst mode'
        ),
        make_option(
            '--worker-class',
            action='store',
            dest='worker_class',
            default='rq.Worker',
            help='RQ Worker class to use'
        ),
        make_option(
            '--name',
            action='store',
            dest='name',
            default=None,
            help='Name of the worker'
        ),
    )
    args = '<queue queue ...>'

    def handle(self, *args, **options):
        try:
            # Instantiate a worker
            worker_class = import_attribute(options.get('worker_class', 'rq.Worker'))
            queues = get_queues(*args)
            w = worker_class(queues, connection=queues[0].connection, name=options['name'])

            # Call use_connection to push the redis connection into LocalStack
            # without this, jobs using RQ's get_current_job() will fail
            use_connection(w.connection)
            w.work(burst=options.get('burst', False))
        except ConnectionError as e:
            print(e)
