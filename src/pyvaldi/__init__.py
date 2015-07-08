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
        if self._next_checkpoint_idx >= len(self.checkpoints):
            next_checkpoint = None
        else:
            next_checkpoint = self.checkpoints[self._next_checkpoint_idx]

        last_checkpoint = self._get_last_thread_checkpoint(
            next_checkpoint, self.checkpoints)

        if next_checkpoint is None:
            runnable_conductor = self._threads[last_checkpoint.starter]
        else:
            runnable_conductor = self._threads[next_checkpoint.starter]

        runnable_conductor.start_or_continue(next_checkpoint, last_checkpoint)

        self._next_checkpoint_idx += 1
        return next_checkpoint

    @staticmethod
    def _get_last_thread_checkpoint(checkpoint, all_checkpoints):
        """Return the last checkpoint on the same thread as this checkpoint"""
        if checkpoint is None:
            return all_checkpoints[-1]

        checkpoint_idx = all_checkpoints.index(checkpoint)

        while checkpoint_idx > 0:
            checkpoint_idx -= 1
            if checkpoint.starter is all_checkpoints[checkpoint_idx].starter:
                return all_checkpoints[checkpoint_idx]

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


class SleepyProfiler(object):
    def __init__(self, checkpoint, condition, checkpoint_reached_callback):
        self.confirming_checkpoints = [checkpoint]
        self.checkpoint_idx = 0
        self.condition = condition
        self.checkpoint_reached_callback = checkpoint_reached_callback

    def __call__(self, frame, action_string, dunno):
        if self.checkpoint_idx >= len(self.confirming_checkpoints):
            return

        current_checkpoint = self.confirming_checkpoints[self.checkpoint_idx]

        if current_checkpoint is None:
            return

        if frame.f_code is not current_checkpoint.get_code():
            return

        if (current_checkpoint.before and action_string == 'call' or
                not current_checkpoint.before and action_string == 'return'):
            self.checkpoint_reached_callback(current_checkpoint)
            self.condition.acquire()
            self.condition.wait()
            self.condition.release()

        self.checkpoint_idx += 1

    def add_checkpoint(self, checkpoint):
        self.confirming_checkpoints.append(checkpoint)


class ProfilingThread(threading.Thread):
    def __init__(self, target, args, kwargs, condition):
        super(ProfilingThread, self).__init__(target=target, args=args, kwargs=kwargs)  # noqa
        self.condition = condition
        self.checkpoint = None
        self.profiler = None
        self._checkpoints_reached = []
        self._checkpoint_edit_lock = threading.Lock()

    def set_checkpoint(self, checkpoint):
        self.checkpoint = checkpoint
        if self.profiler:
            self.profiler.add_checkpoint(checkpoint)

    def run(self):
        self.profiler = SleepyProfiler(
            self.checkpoint, self.condition, self.checkpoint_reached_callback)

        sys.setprofile(self.profiler)
        super(ProfilingThread, self).run()

        # hardcoded...yes... but the None checkpoint means the thread is done
        with open('/tmp/checkpoints', 'w') as f:
            f.write('reached the end')
        self.checkpoint_reached_callback(None)

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
            # wait for the thread to hit the last checkpoint
            while not self.thread.has_reached_checkpoint(last_checkpoint):
                pass

            self.condition.acquire()
            self.condition.notify()
            self.condition.release()

            # if at the end, also wait for the thread to die
            if next_checkpoint is None:
                while not self.thread.has_reached_checkpoint(None):
                    pass

