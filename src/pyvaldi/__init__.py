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
        if self._next_checkpoint_idx > 0:
            last_checkpoint = self.checkpoints[self._next_checkpoint_idx - 1]
        else:
            last_checkpoint = None

        runnable_conductor = self._threads[next_checkpoint.starter]
        runnable_conductor.start_or_continue(next_checkpoint, last_checkpoint)

        self._next_checkpoint_idx += 1
        return next_checkpoint

    def __iter__(self):
        return self



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
    def __init__(self, checkpoint, condition, checkpoint_reached_callback):
        self.checkpoint = checkpoint
        self.condition = condition
        self.checkpoint_reached_callback = checkpoint_reached_callback

    def __call__(self, frame, action_string, dunno):
        if frame.f_code is self.checkpoint.get_code():
            if self.checkpoint.before and action_string == 'call':
                with open('/tmp/before_callback', 'w') as f:
                    f.write(str(self.checkpoint_reached_callback.im_self._checkpoints_reached))
                self.checkpoint_reached_callback(self.checkpoint)
                with open('/tmp/after_callback', 'w') as f:
                    f.write(str(self.checkpoint_reached_callback.im_self._checkpoints_reached))

                self.condition.acquire()
                for _ in range(999):
                    self.condition.wait()
                self.condition.release()

            elif not self.checkpoint.before and action_string == 'return':
                self.checkpoint_reached_callback(self.checkpoint)
                self.condition.acquire()
                for _ in range(999):
                    self.condition.wait()
                self.condition.release()

    def set_checkpoint(self, checkpoint):
        self.checkpoint = checkpoint


class ProfilingThread(threading.Thread):
    def __init__(self, target, args, kwargs, condition):
        super(ProfilingThread, self).__init__(target=target, args=args, kwargs=kwargs)  # noqa
        self.condition = condition
        self.checkpoint = None
        self.profiler = None
        self._checkpoints_reached = []
        self._checkpoint_edit_lock = threading.Lock()

    def set_checkpoint(self, checkpoint):
        # This is the culprit!!! (i think...) This was setting the switch off
        # after it was being set on, causing the controller thread to spin
        # forever on the loop `.has_reached_checkpoint()`
        self.checkpoint = checkpoint
        if self.profiler:
            self.profiler.set_checkpoint(checkpoint)

    def run(self):
        self.profiler = SleepyProfiler(
            self.checkpoint, self.condition, self.checkpoint_reached_callback)

        sys.setprofile(self.profiler)
        super(ProfilingThread, self).run()

    def checkpoint_reached_callback(self, checkpoint):
        self._checkpoint_edit_lock.acquire()
        self._checkpoints_reached.append(checkpoint)
        self._checkpoint_edit_lock.release()

    def has_reached_checkpoint(self, checkpoint):
        self._checkpoint_edit_lock.acquire()
        result = checkpoint in self._checkpoints_reached
        self._checkpoint_edit_lock.release()
        return result


class ThreadConductor(object):
    def __init__(self, target, args, kwargs):
        self.condition = threading.Condition(lock=threading.Lock())
        self.thread = ProfilingThread(
            target=target, args=args, kwargs=kwargs, condition=self.condition)
        self.thread.setDaemon(True)
        self._started = False

    def start_or_continue(self, next_checkpoint, last_checkpoint):
        self.thread.set_checkpoint(next_checkpoint)

        if not self._started:
            self._started = True
            self.thread.start()
            # waiting for the thread to lock on acquire()..hoping it got there
            # by the time we return to this method. this is very likely though
            while not self.thread.has_reached_checkpoint(next_checkpoint):
                pass
        else:
            with open('/tmp/checkpoint_check', 'w') as f:
                f.write(str(self.thread._checkpoints_reached) + ' BUT ' + str(last_checkpoint))
            while not self.thread.has_reached_checkpoint(last_checkpoint):
                pass
            self.condition.acquire()
            self.condition.notify()
            self.condition.release()
