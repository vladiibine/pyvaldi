import unittest

from pyvaldi import ProcessStarter, Runner


class TwoPhaseMachine(object):
    def __init__(self):
        self.steps = []

    def first_phase(self):
        self.steps.append(1)

    def second_phase(self):
        self.steps.append(2)

    def __call__(self, *args, **kwargs):
        self.first_phase()
        self.second_phase()


class TwoThreadsTestCase(unittest.TestCase):
    def test_first_thread_finishes_then_second_starts(self):
        first_machine = TwoPhaseMachine()
        second_machine = TwoPhaseMachine()

        first_starter = ProcessStarter(first_machine)
        cp1 = first_starter.add_checkpoint_after(first_machine.second_phase)

        second_starter = ProcessStarter(second_machine)
        cp2 = second_starter.add_checkpoint_before(second_machine.first_phase)

        runner = Runner([first_starter, second_starter], [cp1, cp2])

        self.assertIs(next(runner), cp1)
        self.assertEqual(first_machine.steps, [1, 2])
        self.assertEqual(second_machine.steps, [])
        self.assertIs(next(runner), cp2)
        self.assertEqual(second_machine.steps, [1, 2])
