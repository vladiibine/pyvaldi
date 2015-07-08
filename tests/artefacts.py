class ThreePhaseMachine(object):
    def __init__(self):
        self.steps = []

    def first_phase(self):
        self.steps.append(1)

    def second_phase(self):
        self.steps.append(2)

    def third_phase(self):
        self.steps.append(3)

    def __call__(self, *args, **kwargs):
        self.first_phase()
        self.second_phase()
        self.third_phase()

    def __repr__(self):
        return u'Machine: {}'.format(self.steps)
