import pkg_resources
import threading
import sys

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
        :param list[Checkpoint] checkpoints: an list of checkpoints (notes)
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
        """Lets the 2 processes run until the next specified checkpoint is reached"""
        notes = self.checkpoints
        implicit_notes = self.music_sheet.checkpoint_order

        while self.note_idx < len(notes):
            while self.implicit_note_idx < len(implicit_notes):
                note = notes[self.note_idx]
                implicit_note = implicit_notes[self.implicit_note_idx]
                # when notes are the same
                if note is implicit_note:
                    self.note_idx += 1
                    self.implicit_note_idx += 1
                    return notes[self.note_idx - 1]
                # when the notes differ
                else:
                    self.baton.yield_permission(implicit_note)
                    # when this returns, the checkpoint has been reached!!!
                    self.baton.wait_acknowledgement(implicit_note)
                    self.implicit_note_idx += 1

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

        :rtype: list[Checkpoint]
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
    def __init__(self, checkpoint_order):
        self.player_event = CascadingEventGroup(checkpoint_order)
        self.conductor_event = CascadingEventGroup(checkpoint_order)

    def wait_for_permission(self, checkpoint):
        self.player_event.wait_on(checkpoint)

    def yield_permission(self, checkpoint):
        self.player_event.done_with(checkpoint)

    def wait_acknowledgement(self, checkpoint):
        self.conductor_event.wait_on(checkpoint)

    def acknowledge_checkpoint(self, checkpoint):
        self.conductor_event.done_with(checkpoint)


class CascadingEventGroup(object):
    """A collection of events, that can only be set in the order specified by
    the token list
    """
    def __init__(self, tokens):
        self.tokens = tokens
        self.token_idx = 0
        self.events = [(token, threading.Event()) for token in tokens]
        self.event_dict = dict(self.events)
        self.release_lock = threading.Lock()

    def wait_on(self, token):
        self.event_dict[token].wait()

    def done_with(self, token):
        # protection for when incrementing and setting the events
        self.release_lock.acquire()
        # protection against wrong token releasing the lock
        if token is not self.events[self.token_idx][1]:
            self.release_lock.release()
            raise threading.ThreadError(
                "At this time, releasing the lock can only be done with "
                "token {}".format(str(self.events[self.token_idx])))
        if self.token_idx + 1 >= len(self.events):
            self.release_lock.release()
            return

        self.token_idx += 1
        self.events[self.token_idx][1].set()
        self.release_lock.release()


class RhythmProfiler(object):
    def __init__(self):
        self.baton = None
        self.checkpoints = None
        self.checkpoint_idx = 0

    def profile(self, frame, action_string, whatever):
        current_cp = self.checkpoints[self.checkpoint_idx]

        if (action_string == 'call' and current_cp.before or
                action_string == 'return' and not current_cp.before):
            if current_cp.is_reached(frame.f_code):
                self.baton.acknowledge_checkpoint(current_cp)

                self.checkpoint_idx += 1
                if self.checkpoint_idx >= len(self.checkpoints):
                    return

                self.baton.wait_for_permission(self.checkpoints[self.checkpoint_idx])

    # def __call__(self, frame, action_string, dunno):
    #     if self.checkpoint_idx >= len(self.confirming_checkpoints):
    #         return
    #
    #     current_checkpoint = self.confirming_checkpoints[self.checkpoint_idx]
    #
    #     if current_checkpoint is None:
    #         return
    #
    #     if not current_checkpoint.is_reached(frame.f_code):
    #         return
    #
    #     if ((current_checkpoint.before and action_string == 'call') or
    #             (not current_checkpoint.before and action_string == 'return')):
    #         self.checkpoint_reached_callback(current_checkpoint)
    #         self.condition.acquire()
    #         self.condition.wait()
    #         self.condition.release()
    #
    #         self.checkpoint_idx += 1


class InstrumentedThread(threading.Thread):
    def __init__(self, group=None, target=None, name=None,
             args=(), kwargs=None, verbose=None):
        super(InstrumentedThread, self).__init__(
            group, target, name, args, kwargs, verbose)
        self.profiler = RhythmProfiler()
        self.baton = None
        self.initial_checkpoint = None
        self.terminal_checkpoint = None

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
        self.baton.yield_permission()

        super(InstrumentedThread, self).run()

        # Allows a player to finish, before allowing new one to start.
        self.baton.wait_for_permission(self.terminal_checkpoint)
        self.baton.yield_permission()


class Checkpoint(object):
    """Represents an instance in the life of a process.

    The :class:`ProcessPlayer` will know to pause all the running processes
    when one of them have reached such a checkpoint
    """
    def __init__(self, player, callable_, before=False, name=None):
        """

        :param ProcessPlayer | None player: The ProcessStarter on which this
            checkpoint was set
        :param callable_: Any callable. Will stop before or after it has been
            called.
        :param bool | None before: whether to stop before or after the callable
            was invoked
        :param str | None name: The name of this checkpoint
            (for easier debugging)
        """
        self.name = name
        self.player = player
        self.callable = callable_
        self.before = before

    def is_reached(self, code):
        """
        :param code: a callable to compare to the managed one
        :rtype: bool
        """
        return self.callable.func_code is code

    def _get_display_name(self):
        return u"'{}'".format(self.name) if self.name is not None else u''

    def __repr__(self):
        return u"<CP {name}of {player} at {id}>".format(
            name=self._get_display_name(), id=id(self), player=self.player)

    def is_initial(self):
        return False

    def is_terminal(self):
        return False

    __str__ = __repr__


class NullCheckpoint(Checkpoint):
    """Special 'Null object' type for checkpoints, so as not to abuse `None`

    Used for specifying that there is no checkpoint.
    """
    def is_reached(self, code):
        """Should never stop at this checkpoint"""
        return False

    def __repr__(self):
        return u"<NULL Checkpoint {name}at {id}>".format(
            name=self._get_display_name(), id=id(self))

    __str__ = __repr__


class ImplicitCheckpoint(Checkpoint):
    """Represents the initial/ terminal implicit points for a process"""
    def __init__(self, player, callable_=None, before=False, name=None):
        super(ImplicitCheckpoint, self).__init__(player, None, before, name)

    def is_reached(self, code):
        """Should always stop at such a checkpoint"""
        return self.before

    def __repr__(self):
        if self.before:
            subtype = u'Init.'
        else:
            subtype = u'Term.'
        return u"<{subtype} CP {name}of {player} at {id}>".format(
            name=self._get_display_name(),
            subtype=subtype,
            id=id(self),
            player=self.player
        )

    __str__ = __repr__

    def __lt__(self, other):
        if not isinstance(other, Checkpoint):
            raise TypeError("Type of {} and {} are not comparable".format(self, other))  # noqa
        if self.player is not other.player:
            raise ValueError("{} and {} have different players".format(self, other))

        return self.before > other.before

    def is_initial(self):
        return self.before

    def is_terminal(self):
        return not self.before

NULL_CHECKPOINT = NullCheckpoint(None, None, None)
