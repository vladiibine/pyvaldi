import pkg_resources
import threading
import sys
import time

try:
    __version__ = pkg_resources.get_distribution('pyvaldi').version
except pkg_resources.DistributionNotFound:
    pass


class ProcessPlayer(object):
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


class ProcessConductor(object):
    """Runs the provided process player objects in parallel, observing the
    checkpoints that were set
    """

    def __init__(self, starters=None, checkpoints=None):
        """
        :param list[ProcessPlayer] starters: a list of process starters
        :param list[Checkpoint] checkpoints: an list of checkpoints
        """
        pass

    def next(self):
        """Lets the 2 processes run until the next specified checkpoint is reached"""
        pass

    def __iter__(self):
        return self


class Checkpoint(object):
    """Represents an instance in the life of a process.

    The :class:`Runner` will know to pause all the running processes when one
    of them has reached such a checkpoint
    """
    def __init__(self, starter, callable_, before=False, name=None):
        """

        :param ProcessPlayer | None starter: The ProcessStarter on which this
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
