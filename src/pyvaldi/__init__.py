__version__ = "0.1.0"


class ProcessStarter(object):
    """Starts a process, and sets Checkpoints in its lifecycle"""
    def __init__(self, callable_, *args, **kwargs):
        self.callable = callable_
        self.args = args
        self.kwargs = kwargs

    def add_checkpoint_after(self, callable_):
        """Create and return a checkpoint, set AFTER the callable returns"""
        raise NotImplementedError

    def add_checkpoint_before(self, callable_):
        """Create and return a checkpoint, set BEFORE the callable returns"""
        raise NotImplementedError


class Runner(object):
    """Runs the provided process starter objects in parallel, observing the
    checkpoints that were set
    """
    def __init__(self, starters=None, checkpoints=None):
        """

        :param list[ProcessStarter] starters: a list of process starters
        :param checkpoints:
        :return:
        """
        self.starters = starters

    def next(self):
        """Lets the 2 processes run until the next checkpoint is reached
        """
        raise NotImplementedError


class Checkpoint(object):
    """Represents an instance in the life of a process.

    The :class:`Runner` will know to pause all the running processes when one
    of them has reached such a checkpoint
    """
    pass
