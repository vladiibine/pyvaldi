__version__ = "0.1.0"


import threading
import sys


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
            starter: ThreadConductor(
                target=starter.callable,
                args=starter.args,
                kwargs=starter.kwargs)
            for starter in starters
        }

    def next(self):
        """Lets the 2 processes run until the next checkpoint is reached """
        next_checkpoint = self.checkpoints[self._next_checkpoint_idx]

        runnable_conductor = self._threads[next_checkpoint.starter]
        self._run_to_checkpoint(runnable_conductor, next_checkpoint)

        self._next_checkpoint_idx += 1
        return next_checkpoint

    def __iter__(self):
        return self

    def _run_to_checkpoint(self, conductor, checkpoint):
        """Allow the thread to run until the checkpoint is reached

        :param ThreadConductor conductor: the thread to run
        :param Checkpoint checkpoint: checkpoint at which execution will once
            again stop
        """
        conductor.start_or_continue(checkpoint)


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


def create_sleepy_profiler(checkpoint, condition):
    """
    :param Checkpoint checkpoint: the ckeckpoint where the profiler will wait
    :param threading.Condition condition: to use for signaling the checkpoint
        has been reached
    :return: a callable to set as the system profiler
    """
    def profiler(frame, action_string, dunno):
        if frame.f_code is checkpoint.get_code():
            if checkpoint.before and action_string == 'call':
                condition.notify()
            elif not checkpoint.before and action_string == 'return':
                condition.notify()

    if checkpoint:
        return profiler


class SleepyProfiler(object):
    def __init__(self, checkpoint, condition, wait_callback):
        self.checkpoint = checkpoint
        self.condition = condition
        self.wait_callback = wait_callback

    def __call__(self, frame, action_string, dunno):
        if frame.f_code is self.checkpoint.get_code():
            if self.checkpoint.before and action_string == 'call':
                self.wait_callback()
                raise Exception('asdf')
                self.condition.acquire()
                self.condition.release()
                # self.condition.notify()
                # self.condition.wait()
                pass

            elif not self.checkpoint.before and action_string == 'return':
                self.wait_callback()
                raise Exception('zxcv')
                self.condition.acquire()
                self.condition.release()
                # self.condition.notify()
                # self.condition.wait()
                pass

    def set_checkpoint(self, checkpoint):
        self.checkpoint = checkpoint


class ProfilingThread(threading.Thread):
    def __init__(self, target, args, kwargs, condition):
        super(ProfilingThread, self).__init__(target=target, args=args, kwargs=kwargs)  # noqa
        self.condition = condition
        self.checkpoint = None
        self.checkpoint_reached = False
        self.profiler = None

    def set_checkpoint(self, checkpoint):
        self.checkpoint_reached = False
        self.checkpoint = checkpoint
        if self.profiler:
            self.profiler.set_checkpoint(checkpoint)

    def run(self):
        self.profiler = SleepyProfiler(
            self.checkpoint, self.condition, self.wait_wallback)

        sys.setprofile(self.profiler)
        super(ProfilingThread, self).run()

    def wait_wallback(self):
        self.checkpoint_reached = True

    def has_reached_checkpoint(self):
        return self.checkpoint_reached


class ThreadConductor(object):
    def __init__(self, target, args, kwargs):
        self.condition = threading.Condition()
        self.condition.acquire()
        self.thread = ProfilingThread(
            target=target, args=args, kwargs=kwargs, condition=self.condition)
        self.thread.setDaemon(True)
        self._started = False

    def start_or_continue(self, checkpoint):
        self.thread.set_checkpoint(checkpoint)

        if not self._started:
            self._started = True
            self.thread.start()
            # waiting for the thread to lock on acquire()..hoping it got there
            # by the time we return to this method. this is very likely though
            while not self.thread.has_reached_checkpoint():
                pass
        else:
            self.condition.release()
            while not self.thread.has_reached_checkpoint():
                pass

            raise Exception('1234')
            self.condition.acquire()
