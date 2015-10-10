import threading

import pkg_resources

from pyvaldi.checkpoints import Checkpoint, NullCheckpoint, ImplicitCheckpoint
from pyvaldi.sync import CascadingEventGroup
from pyvaldi.thread import InstrumentedThread

try:
    __version__ = pkg_resources.get_distribution('pyvaldi').version
except pkg_resources.DistributionNotFound:
    pass

log_lock = threading.Lock()
from .stacktracer import trace_start
trace_start('/tmp/trace')

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
        self.music_sheet = None
        self._terminal_checkpoint = ImplicitCheckpoint(self, None)
        self._initial_checkpoint = ImplicitCheckpoint(self, None, before=True)
        self.instrument = InstrumentedThread(
            target=callable_, args=args_for_callable, kwargs=kwargs_for_callable)

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

    def play(self, player_checkpoints, baton):
        self.music_sheet = player_checkpoints
        self.instrument.tune(baton, player_checkpoints)
        self.instrument.start()

    def __repr__(self):
        return u"<Player {}>".format(self.name)

    __str__ = __repr__


class ProcessConductor(object):
    """Runs the provided process player objects in parallel, observing the
    checkpoints that were set
    """

    def __init__(self, players=None, checkpoints=None):
        """
        :param list[ProcessPlayer] players: a list of process players
        :param list[pyvaldi.checkpoints.Checkpoint] checkpoints: an list of
        checkpoints (notes)
        """
        self.players = players
        self.checkpoints = checkpoints

        self.note_idx = 0
        self.implicit_note_idx = 0

        self.music_sheet = MusicSheet(checkpoints)
        self.baton = Baton(self.music_sheet.checkpoint_order)

        for player in players:
            player.play(self.music_sheet.player_checkpoints(player), self.baton)

    def next(self):
        """
        User CPS:       C1-1       C2-1   C1-2   C2-2   C2-3   C2-4         C1-3
        Impli CPS: IC1  C1-1  IC2  C2-1   C1-2   C2-2   C2-3   C2-4   TC2   C1-3   TC1

        Restrict!
            - always enter on user note
            - increase implicit index, until meeting the user note
        """
        notes = self.checkpoints
        i_notes = self.music_sheet.checkpoint_order
        if self.note_idx >= len(notes):
            return

        while i_notes[self.implicit_note_idx] is not notes[self.note_idx]:
            self.baton.yield_permission(i_notes[self.implicit_note_idx])
            self.baton.wait_acknowledgement(i_notes[self.implicit_note_idx])
            self.implicit_note_idx += 1
            if self.implicit_note_idx >= len(i_notes):
                return
        else:
            try:
                return notes[self.note_idx]
            finally:
                self.note_idx += 1

    def __iter__(self):
        return self


class MusicSheet(object):
    """Determine the order in which checkpoints should be reached
    """
    def __init__(self, checkpoints):
        self.checkpoint_order = self.determine_checkpoint_order(checkpoints)

    def player_checkpoints(self, player):
        return [cp for cp in self.checkpoint_order if cp.player is player]

    def determine_checkpoint_order(self, checkpoints):
        """Return a list of players, representing the order they should be
        allowed to play in.

        :rtype: list[pyvaldi.checkpoints.Checkpoint]
        """
        # We'll receive a list of checkpoints...
        # MAYBE containing the implicit checkpoints already
        players = set(cp.player for cp in checkpoints)
        # Eliminate the implicit ones.. we'll determine those
        checkpoints = [cp for cp in checkpoints
                       if not isinstance(cp, ImplicitCheckpoint)]

        raw_player_cps = {}  # {player: list[Checkpoints]}
        for player in players:
            raw_player_cps[player] = [
                cp for cp in checkpoints if cp.player is player
            ]

        actual_player_cps = {}  # {player: list[Checkpoints]}
        for player in players:
            actual_player_cps[player] = (
                [player.get_initial_checkpoint()] +
                list(raw_player_cps[player]) +
                [player.get_terminal_checkpoint()])

        # Merge stage...
        result_checkpoints = []
        for reference_cp in checkpoints:
            player_cps = actual_player_cps[reference_cp.player]
            result_checkpoints.extend(
                player_cps[0:player_cps.index(reference_cp) + 1])
            player_cps[0:player_cps.index(reference_cp) + 1] = []

            # Append the terminal CP of some single player
            if len(player_cps) == 1:
                result_checkpoints.append(player_cps[0])

        # the order in which the players will be allowed to play
        return result_checkpoints


class Baton(object):
    """The Conductor's instrument for synchronizing the players.
    """
    def log(self, cp):
        log_lock.acquire()
        import inspect
        func_name = inspect.currentframe().f_back.f_code.co_name
        print("{} in {} waiting on {}".format(threading.current_thread().name, func_name, cp))
        log_lock.release()

    def __init__(self, checkpoint_order):
        self.player_event = CascadingEventGroup(checkpoint_order, 'player evt.')
        self.conductor_event = CascadingEventGroup(checkpoint_order, 'conductor evt')
        self.log_lock = threading.Lock()

    def wait_for_permission(self, checkpoint):
        # self.log(checkpoint)
        self.player_event.wait_on(checkpoint)

    def yield_permission(self, checkpoint):
        # self.log(checkpoint)
        self.player_event.done_with(checkpoint)

    def wait_acknowledgement(self, checkpoint):
        # self.log(checkpoint)
        self.conductor_event.wait_on(checkpoint)

    def acknowledge_checkpoint(self, checkpoint):
        # self.log(checkpoint)
        self.conductor_event.done_with(checkpoint)


