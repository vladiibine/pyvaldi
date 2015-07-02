__version__ = "0.1.0"


import threading


class ProcessStarter(object):
    """Starts a process, and sets Checkpoints in its lifecycle"""
    def __init__(self, callable_, *args, **kwargs):
        self.callable = callable_
        self.args = args
        self.kwargs = kwargs
        self.event = None

    def add_checkpoint_after(self, callable_):
        """Create and return a checkpoint, set AFTER the callable returns"""
        return Checkpoint(self, callable_)

    def add_checkpoint_before(self, callable_):
        """Create and return a checkpoint, set BEFORE the callable returns"""
        return Checkpoint(self, callable_, before=True)


class Runner(object):
    """Runs the provided process starter objects in parallel, observing the
    checkpoints that were set
    """
    def __init__(self, starters=None, checkpoints=None):
        """
        :param list[ProcessStarter] starters: a list of process starters
        :param list[Checkpoint] checkpoints: an list of checkpoints
        """
        self.starters = starters
        self.checkpoints = checkpoints
        self._next_checkpoint_idx = 0
        self._threads = {
            starter: StartAwareThread(
                target=starter.callable,
                args=starter.args,
                kwargs=starter.kwargs)
            for starter in starters
        }

    def next(self):
        """Lets the 2 processes run until the next checkpoint is reached """
        next_checkpoint = self.checkpoints[self._next_checkpoint_idx]

        runnable_thread = self._threads[next_checkpoint.starter]
        self._run_to_checkpoint(runnable_thread, next_checkpoint)

        self._next_checkpoint_idx += 1
        return next_checkpoint

    def __iter__(self):
        return self

    def _run_to_checkpoint(self, thread, checkpoint):
        """Allow the thread to run until the checkpoint is reached

        :param SleepyThread thread: the thread to run
        :param checkpoint: checkpoint at which execution will once again stop
        """
        if not thread.is_started():
            thread.start()


class Checkpoint(object):
    """Represents an instance in the life of a process.

    The :class:`Runner` will know to pause all the running processes when one
    of them has reached such a checkpoint
    """
    def __init__(self, starter, callable_, before=False):
        self.starter = starter
        self.callable = callable_
        self.before = before

    def get_code(self):
        return self.callable.func_code


class StartAwareThread(threading.Thread):
    """A thread that knows whether it was started or not"""
    def __init__(self, *args, **kwargs):
        super(StartAwareThread, self).__init__(*args, **kwargs)
        self._started = False

    def start(self):
        self._started = True
        super(StartAwareThread, self).start()

    def is_started(self):
        return self._started


class SleepyThread(StartAwareThread):
    """Thread that can be woken up to run until the next checkpoint"""
    def __init__(self, *args, **kwargs):
        super(SleepyThread, self).__init__(*args, **kwargs)
        self.event = threading.Event()

    def wake_up(self):
        pass
