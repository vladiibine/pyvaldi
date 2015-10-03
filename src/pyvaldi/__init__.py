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

    def play(self, baton):
        self.instrument.tune(baton, self)
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
        :param list[Checkpoint] checkpoints: an list of checkpoints
        """
        self.players = players
        self.checkpoints = checkpoints

        self.baton = Baton(checkpoints)
        for player in players:
            player.play(self.baton)



    def next(self):
        """Lets the 2 processes run until the next specified checkpoint is reached"""
        pass

    def __iter__(self):
        return self


class Baton(object):
    """The Conductor's instrument for synchronizing the players.

    A Lock, that knows who should play next
    """
    def __init__(self, checkpoints):
        self.player_order = self.determine_player_order(checkpoints)

    def determine_player_order(self, checkpoints):
        """Return a list of players, representing the order they should be
        allowed to play in.
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
                [ImplicitCheckpoint(player, before=True)] +
                list(raw_player_cps[player]) +
                [ImplicitCheckpoint(player)])

        # Merge stage...
        result_checkpoints = []
        for idx, reference_cp in enumerate(checkpoints):
            player_cps = actual_player_cps[reference_cp.player]
            result_checkpoints.extend(
                player_cps[0:player_cps.index(reference_cp) + 1])
            player_cps[0:player_cps.index(reference_cp) + 1] = []

            # Append the terminal CP of some single player
            if len(player_cps) == 1:
                result_checkpoints.append(player_cps[0])

        # the order in which the players will be allowed to play
        return [cp.player for cp in result_checkpoints]

    def ask_for_permission(self, player):
        pass

    def yield_permission(self, player):
        pass


class RhythmProfiler(object):
    def __init__(self):
        self.baton = None
        self.player = None

    def profile(self, frame, action_string, whatever):
        # IF CHECKPOINT REACKED
        # if entering, ask for permission
        self.baton.wait_for_permission(self.player)

        # if returning, yield permission
        self.baton.yield_permission(self.player)


    # def __call__(self, frame, action_string, dunno):
    #     if self.checkpoint_idx >= len(self.confirming_checkpoints):
    #         return
    #
    #     current_checkpoint = self.confirming_checkpoints[self.checkpoint_idx]
    #
    #     if current_checkpoint is None:
    #         return
    #
    #     if not current_checkpoint.should_stop(frame.f_code):
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
        self.player = None

    def tune(self, baton, player):
        self.profiler.baton = baton
        self.profiler.player = player
        self.baton = baton

    def run(self):
        sys.setprofile(self.profiler.profile)

        # Check the initial checkpoint. Decide the order in which players start
        self.baton.wait_for_permission(self.player)
        self.baton.yield_permission(self.player)

        super(InstrumentedThread, self).run()

        # Allows a player to finish, before allowing new one to start.
        self.baton.wait_for_permission(self.player)
        self.baton.yield_permission(self.player)


class Checkpoint(object):
    """Represents an instance in the life of a process.

    The :class:`ProcessPlayer` will know to pause all the running processes
    when one of them has reached such a checkpoint
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

    def should_stop(self, code):
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
    def should_stop(self, code):
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

    def should_stop(self, code):
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
