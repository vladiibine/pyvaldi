import threading


class CascadingEventGroup(object):
    """A collection of events, that can only be set in the order specified by
    the token list
    """
    def __init__(self, tokens, name=None):
        self.tokens = tokens
        self.name = name

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
        if token is not self.events[self.token_idx][0]:
            self.release_lock.release()
            raise threading.ThreadError(
                "At this time, releasing the lock can only be done with "
                "token {}".format(str(self.events[self.token_idx][0])))
        if self.token_idx + 1 > len(self.events):
            self.release_lock.release()
            return

        self.token_idx += 1
        self.events[self.token_idx - 1][1].set()
        self.release_lock.release()

    def __repr__(self):
        return u"<CEG {}>".format(self.name if self.name else '')