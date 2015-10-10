import sys
import threading
from pyvaldi.profiler import RhythmProfiler
from pyvaldi.checkpoints import ImplicitCheckpoint


class InstrumentedThread(threading.Thread):
    def __init__(self, group=None, target=None, name=None,
             args=(), kwargs=None, verbose=None):
        super(InstrumentedThread, self).__init__(
            group, target, name, args, kwargs, verbose)
        self.profiler = RhythmProfiler()
        self.baton = None
        self.initial_checkpoint = None
        self.terminal_checkpoint = None
        self.setDaemon(True)

    def tune(self, baton, checkpoints):
        self.profiler.baton = baton
        # the profiler handles the regular checkpoints, and
        # the thread - the implicit ones
        self.initial_checkpoint = checkpoints[0]
        self.terminal_checkpoint = checkpoints[-1]
        self.profiler.checkpoints = [
            cp for cp in checkpoints if not isinstance(cp, ImplicitCheckpoint)]
        self.baton = baton

    def run(self):
        sys.setprofile(self.profiler.profile)

        # Check the initial checkpoint. Decide the order in which players start
        self.baton.wait_for_permission(self.initial_checkpoint)
        self.baton.acknowledge_checkpoint(self.initial_checkpoint)

        super(InstrumentedThread, self).run()

        # Allows a player to finish, before allowing new one to start.
        self.baton.wait_for_permission(self.terminal_checkpoint)
        self.baton.acknowledge_checkpoint(self.terminal_checkpoint)