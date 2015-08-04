__version__ = "0.1.0"


import threading
import sys
import time


class ProcessStarter(object):
    """Starts a process, and sets Checkpoints in its lifecycle"""
    def __init__(self, callable_, *args, **kwargs):
        self.callable = callable_
        self.args = args
        self.kwargs = kwargs
        self.event = None
        self._terminal_checkpoint = ImplicitCheckpoint(self, None)
        self._initial_checkpoint = ImplicitCheckpoint(self, None, before=True)

    def add_checkpoint_after(self, callable_, name=None):
        """Create and return a checkpoint, set AFTER the callable returns"""
        return Checkpoint(self, callable_, name=name)

    def add_checkpoint_before(self, callable_, name=None):
        """Create and return a checkpoint, set BEFORE the callable returns"""
        return Checkpoint(self, callable_, before=True, name=name)

    def get_terminal_checkpoint(self):
        """Returns a checkpoint that marks the process end"""
        return self._terminal_checkpoint

    def get_initial_checkpoint(self):
        """Return the initial checkpoint, that marks the process beginning"""
        return self._initial_checkpoint


def get_previous_checkpoint_on_starter(checkpoints, checkpoint_idx):
    """Return the previous checkpoint on the same starter as this one
    :param list[Checkpoint] checkpoints: ordered list of checkpoints
    :param int checkpoint_idx: the index of the current checkpoint
    :rtype: Checkpoint
    """
    starter = checkpoints[checkpoint_idx].starter

    for candidate in reversed(checkpoints[0:checkpoint_idx]):
        if candidate.starter is starter:
            return candidate

    return starter.get_initial_checkpoint()


def generate_checkpoint_pairs(checkpoints, next_idx):
    """Between 2 given checkpoints, inserts the implicit initial/ terminal ones

    Always returns a pair of checkpoints set on the same starter.

     switching from 1 to 2, but we're not done with 1
     p1:  1   2               3          TERM
     p2:          INIT 1    2            TERM
     last = p1c2; next = p2c1
         yield p2.cp1, p2.INITIAL

     switching from 1 to 2, but we're done with 1
     p1:  1    2                       TERM
     p2:           INIT   1    2       TERM
     last = p1c2; next = p2c1
         yield p1.TERMINAL, p1c2
         yield p2c1; p2.INITIAL

     switching back to 1, done with 2
     p1: 1       2              TERM
     p2:    1                   TERM
     last = p2.c1; next = p1.c2
        yield p2.term, p2.c1
        yield p1.c2, p1.c1

    switching back to 1, NOT done with 2
    p1: 1       2        TERM
    p2:    1         2   TERM
    last = p2.c1; next = p1.c2
       yield p1.c2, p1.c1


    :param list[Checkpoint] checkpoints: ordered list of checkpoints
    :param next_idx: the index of the next checkpoint that should be reached
    :return: tuple (next_checkpoint, last_checkpoint)
    """
    if next_idx == len(checkpoints):
        yield checkpoints[-1].starter.get_terminal_checkpoint(), checkpoints[-1]
        raise StopIteration

    if next_idx == 0:
        yield checkpoints[0], NULL_CHECKPOINT
        raise StopIteration

    if next_idx > len(checkpoints):
        raise StopIteration

    last_checkpoint = checkpoints[next_idx - 1]
    next_checkpoint = checkpoints[next_idx]

    if last_checkpoint.starter is next_checkpoint.starter:
        yield next_checkpoint, last_checkpoint
        raise StopIteration

    for checkpoint in checkpoints[next_idx:]:
        # Not done with the last thread
        if checkpoint.starter is last_checkpoint.starter:
            yield (next_checkpoint,
                   get_previous_checkpoint_on_starter(checkpoints, next_idx))
            break
    else:
        # Done with the last thread. Insert its terminal checkpoint
        yield (
            last_checkpoint.starter.get_terminal_checkpoint(),
            last_checkpoint
        )
        yield (
            next_checkpoint,
            get_previous_checkpoint_on_starter(checkpoints, next_idx)
        )


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
                kwargs=starter.kwargs,
                terminal_checkpoint=starter.get_terminal_checkpoint()
            )
            for starter in starters
        }
        self._order_generator = generate_checkpoint_pairs

    def next(self):
        """Lets the 2 processes run until the next specified checkpoint is reached"""
        sentinel = actual_next = object()

        for actual_next, actual_last in self._order_generator(
                self.checkpoints, self._next_checkpoint_idx):
            self._run_single_step(actual_last, actual_next)

        self._next_checkpoint_idx += 1
        if actual_next is not sentinel:
            return actual_next
        else:
            return NULL_CHECKPOINT

    def _run_single_step(self, last_checkpoint, next_checkpoint):
        runnable_conductor = self._get_runnable_conductor(
            last_checkpoint, next_checkpoint)
        runnable_conductor.start_or_continue(next_checkpoint)

    def _get_runnable_conductor(self, last_checkpoint, next_checkpoint):
        """Return the ThreadConductor that should run next"""
        if next_checkpoint is None:
            runnable_conductor = self._threads[last_checkpoint.starter]
        else:
            runnable_conductor = self._threads[next_checkpoint.starter]
        return runnable_conductor

    @classmethod
    def _get_next_and_last_checkpoint(cls, checkpoints, next_checkpoint_idx):
        """Return the next checkpoints to hit and the one previous to it

        Both checkpoints are set on the same starter
        """
        if next_checkpoint_idx >= len(checkpoints):
            next_checkpoint = None
        else:
            next_checkpoint = checkpoints[next_checkpoint_idx]

        last_checkpoint = cls._get_last_thread_checkpoint(
            next_checkpoint, checkpoints)

        return next_checkpoint, last_checkpoint

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
    def __init__(self, starter, callable_, before=False, name=None):
        """

        :param ProcessStarter | None starter: The ProcessStarter on which this
            checkpoint was set
        :param callable_: Any callable. Will stop before or after it has been
            called.
        :param bool | None before: whether to stop before or after the callable
            was invoked
        :param str | None name: The name of this checkpoint
            (for easier debugging)
        """
        self.name = name
        self.starter = starter
        self.callable = callable_
        self.before = before

    def should_stop(self, code):
        """
        :param code: a callable to compare to the managed one
        :rtype: bool
        """
        return self.callable.func_code is code

    def _get_display_name(self):
        return u"'{}'".format(self.name) if self.name is not None else u''

    def __repr__(self):
        return u"<CP {name}at {id}>".format(
            name=self._get_display_name(), id=id(self))

    __str__ = __repr__


class NullCheckpoint(Checkpoint):
    """Special 'Null object' type for checkpoints, so as not to abuse `None`

    Used for specifying that there is no checkpoint.
    """
    def should_stop(self, code):
        """Should never stop at this checkpoint"""
        return False

    def __repr__(self):
        return u"<NULL Checkpoint {name}at {id}>".format(
            name=self._get_display_name(), id=id(self))

    __str__ = __repr__


class ImplicitCheckpoint(Checkpoint):
    """Represents the initial/ terminal implicit points for a process"""
    def should_stop(self, code):
        """Should always stop at such a checkpoint"""
        return True

    def __repr__(self):
        return u"<Implicit Checkpoint {name}at {id}>".format(
            name=self._get_display_name(), id=id(self))


NULL_CHECKPOINT = NullCheckpoint(None, None, None)


class SleepyProfiler(object):
    """Profiler that will wait when it reaches a certain checkpoint """
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

        if not current_checkpoint.should_stop(frame.f_code):
            return

        if ((current_checkpoint.before and action_string == 'call') or
                (not current_checkpoint.before and action_string == 'return')):
            self.checkpoint_reached_callback(current_checkpoint)
            self.condition.acquire()
            self.condition.wait()
            self.condition.release()

            self.checkpoint_idx += 1

    def add_checkpoint(self, checkpoint):
        """Set a new checkpoint where the profiler should wait """
        self.confirming_checkpoints.append(checkpoint)


class SleepingThread(threading.Thread):
    """Thread that will stop and sleep at the checkpoints specified """
    def __init__(self, target, args, kwargs, condition, terminal_checkpoint):
        super(SleepingThread, self).__init__(target=target, args=args, kwargs=kwargs)  # noqa
        self.condition = condition
        self.checkpoint = None
        self.profiler = None
        self.terminal_checkpoint = terminal_checkpoint
        self._checkpoints_reached = []
        self._checkpoint_edit_lock = threading.Lock()

    def set_checkpoint(self, checkpoint):
        """Specify a checkpoint that when reached, will cause the thread to sleep
        """
        self.checkpoint = checkpoint
        if self.profiler:
            self.profiler.add_checkpoint(checkpoint)

    def run(self):
        self.profiler = SleepyProfiler(
            self.checkpoint, self.condition, self.confirm_checkpoint_reached)

        sys.setprofile(self.profiler)
        super(SleepingThread, self).run()

        # self.confirm_checkpoint_reached(self.terminal_checkpoint)
        self.confirm_checkpoint_reached(None)

    def confirm_checkpoint_reached(self, checkpoint):
        self._checkpoint_edit_lock.acquire()
        self._checkpoints_reached.append(checkpoint)
        self._checkpoint_edit_lock.release()

    def has_reached_checkpoint(self, checkpoint):
        self._checkpoint_edit_lock.acquire()
        result = checkpoint in self._checkpoints_reached
        self._checkpoint_edit_lock.release()
        return result


class ThreadConductor(object):
    """Allows a thread to run intermittently (until it reaches checkpoints) """
    def __init__(self, target, args, kwargs, terminal_checkpoint):
        # We wouldn't want the default re-entrant lock now, would we?
        self.condition = threading.Condition(lock=threading.Lock())
        self.thread = SleepingThread(
            target=target,
            args=args,
            kwargs=kwargs,
            condition=self.condition,
            terminal_checkpoint=terminal_checkpoint
        )
        self.thread.setDaemon(True)
        self._started = False

    def start_or_continue(self, next_checkpoint):
        """Lets associated thread run until it reaches the :param:`next_checkpoint`

        :param Checkpoint next_checkpoint: the next checkpoint that must be
            reached
        """
        # TODO - next_checkpoint will never be none here. We'll only
        # get regular and terminal checkpoints
        # (maybe initial checkpoints? we don't have those yet)
        self.thread.set_checkpoint(next_checkpoint)

        if not self._started:
            self._started = True
            # Start
            self.thread.start()
            # Join
            while not self.thread.has_reached_checkpoint(next_checkpoint) and self.thread.is_alive():
                time.sleep(0.1)
        else:
            self.condition.acquire()
            # Notify other thread to continue its execution
            self.condition.notify()
            self.condition.release()

            # wait for the thread to hit the current checkpoint (Join)
            while not self.thread.has_reached_checkpoint(next_checkpoint) and self.thread.is_alive():
                time.sleep(0.1)
