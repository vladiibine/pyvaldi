__version__ = "0.1.0"


import threading
import sys
import time


class ProcessStarter(object):
    """Starts a process, and sets Checkpoints in its lifecycle"""
    def __init__(self, callable_, name="nameless", *args_for_callable, **kwargs_for_callable):
        """
        :param callable_:
        :param str name: The name of this :class:`ProcessStarter`
        :param args_for_callable:
        :param kwargs_for_callable:
        :return:
        """
        self.name = name
        self.callable = callable_
        self.args = args_for_callable
        self.kwargs = kwargs_for_callable
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

    def __repr__(self):
        return u"<Starter {}>".format(self.name)

    __str__ = __repr__


def get_previous_checkpoint_on_starter(checkpoints, checkpoint_idx):
    """Return the previous checkpoint on the same starter as this one
    :param list[Checkpoint] checkpoints: ordered list of checkpoints
    :param int checkpoint_idx: the index of the current checkpoint
    :rtype: Checkpoint
    """
    if checkpoint_idx >= len(checkpoints):
        return checkpoints[-1].starter.get_terminal_checkpoint()

    starter = checkpoints[checkpoint_idx].starter


    for candidate in reversed(checkpoints[0:checkpoint_idx]):
        if candidate.starter is starter:
            return candidate

    return starter.get_initial_checkpoint()


class OrderedSet(list):
    def __init__(self, iterable):
        proper_elems = []
        for elem in iterable:
            if elem not in proper_elems:
                proper_elems.append(elem)
        super(OrderedSet, self).__init__(iterable)


class ImplicitCheckpointInterpolator(object):
    """Given a list of user defined checkpoints, adds the implicit ones.

    Implicit means the initial and terminal checkpoints.
    This is done in order to properly switch between threads.
    """
    def __init__(self, checkpoints):
        self.starters = OrderedSet([cp.starter for cp in checkpoints])
        self.starter_checkpoints = {
            starter: sorted(
                [cp for cp in checkpoints
                 if cp.starter is starter
                 and isinstance(cp, ImplicitCheckpoint)]
            )
            for starter in self.starters
        }
        self.checkpoints = list(checkpoints)

    def interpolate(self):
        """Return a list of checkpoints with all implicit ones present

        :rtype: list[Checkpoint]
        """
        for starter, implicits in self.starter_checkpoints.items():
            if len(implicits) == 2:
                continue
            elif len(implicits) == 1:
                implicit_checkpoint = implicits[0]
                missing_checkpoint = ImplicitCheckpoint(
                    starter=implicit_checkpoint.starter,
                    callable_=None,
                    before=not implicit_checkpoint.before,
                )
                self.insert_missing(missing_checkpoint, starter, self.checkpoints)  # noqa
            elif len(implicits) == 0:
                for before in (True, False):
                    self.insert_missing(
                        ImplicitCheckpoint(starter, None, before),
                        starter,
                        self.checkpoints
                    )

        return self.checkpoints

    @staticmethod
    def insert_missing(missing, starter, checkpoints):
        """Insert the missing implicit checkpoint in the checkpoint list

        :param ImplicitCheckpoint missing: the missing CP for its starter
        :param ProcessStarter starter: the starter we were talking about
        :param list[Checkpoint] checkpoints: the checkpoint list
        """
        # Where to insert an initial checkpoint?
        # > Before the first checkpoint of its starter
        # > Also a terminal checkpoint should be inserted after the last CP on
        starter_checkpoints = [cp for cp in checkpoints
                               if cp.starter is starter]

        if missing.before:
            first_idx = checkpoints.index(starter_checkpoints[0])
            checkpoints.insert(first_idx, missing)
        else:
            last_idx = checkpoints.index(starter_checkpoints[-1])
            checkpoints.insert(last_idx + 1, missing)


class Runner(object):
    """Runs the provided process starter objects in parallel, observing the
    checkpoints that were set
    """
    # Deprecated. Makes is hard to handle terminal nodes that really are at the
    # _order_generator = staticmethod(generate_checkpoint_pairs)
    _get_actual_checkpoints = 0

    def __init__(self, starters=None, checkpoints=None):
        """
        :param list[ProcessStarter] starters: a list of process starters
        :param list[Checkpoint] checkpoints: an list of checkpoints
        """
        self.starters = starters
        self.user_checkpoints = checkpoints
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
        self._checkpoints_including_implicit = (
            ImplicitCheckpointInterpolator(self.user_checkpoints).interpolate()
        )

    def next(self):
        """Lets the 2 processes run until the next specified checkpoint is reached"""
        all_checkpoints = self._checkpoints_including_implicit

        if self._next_checkpoint_idx >= len(all_checkpoints):
            return

        checkpoint = all_checkpoints[self._next_checkpoint_idx]
        self._next_checkpoint_idx += 1
        while checkpoint not in self.user_checkpoints:
            last_checkpoint = get_previous_checkpoint_on_starter(
                all_checkpoints, self._next_checkpoint_idx)
            self._run_single_step(last_checkpoint, checkpoint)
            if self._next_checkpoint_idx >= len(all_checkpoints):
                return
            checkpoint = all_checkpoints[self._next_checkpoint_idx]
            self._next_checkpoint_idx += 1

        return checkpoint

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
        return u"<CP {name}of {starter} at {id}>".format(
            name=self._get_display_name(), id=id(self), starter=self.starter)

    def is_initial(self):
        return False

    def is_terminal(self):
        return False

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
        return self.before

    def __repr__(self):
        if self.before:
            subtype = u'Init.'
        else:
            subtype = u'Term.'
        return u"<{subtype} CP {name}of {starter} at {id}>".format(
            name=self._get_display_name(),
            subtype=subtype,
            id=id(self),
            starter=self.starter
        )

    __str__ = __repr__

    def __lt__(self, other):
        if not isinstance(other, Checkpoint):
            raise TypeError("Type of {} and {} are not comparable".format(self, other))  # noqa
        if self.starter is not other.starter:
            raise ValueError("{} and {} have different starters".format(self, other))

        return self.before > other.before

    def is_initial(self):
        return self.before

    def is_terminal(self):
        return not self.before

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
