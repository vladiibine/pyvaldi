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