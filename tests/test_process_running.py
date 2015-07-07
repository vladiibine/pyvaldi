import unittest

from pyvaldi import ProcessStarter, Runner

from .artefacts import ThreePhaseMachine


class SingleThreadTestCase(unittest.TestCase):
    def test_thread_state_changes_after_each_checkpoint(self):
        machine = ThreePhaseMachine()

        starter = ProcessStarter(machine)

        cp1 = starter.add_checkpoint_before(machine.first_phase)
        cp2 = starter.add_checkpoint_before(machine.second_phase)
        cp3 = starter.add_checkpoint_before(machine.third_phase)
        cp4 = starter.add_checkpoint_after(machine.third_phase)

        runner = Runner([starter], [cp1, cp2, cp3, cp4])

        self.assertEqual(machine.steps, [])
        next(runner)
        self.assertEqual(machine.steps, [])
        next(runner)
        self.assertEqual(machine.steps, [1])
        next(runner)
        self.assertEqual(machine.steps, [1, 2])
        next(runner)
        self.assertEqual(machine.steps, [1, 2, 3])

    def test_run_to_first_checkpoint(self):
        machine = ThreePhaseMachine()
        starter = ProcessStarter(machine)
        cp = starter.add_checkpoint_before(machine.third_phase)

        runner = Runner([starter], [cp])

        next(runner)
        self.assertEqual(machine.steps, [1, 2])


class TwoThreadsTestCase(unittest.TestCase):
    def test_first_thread_finishes_then_second_starts(self):
        first_machine = ThreePhaseMachine()
        second_machine = ThreePhaseMachine()

        first_starter = ProcessStarter(first_machine)
        cp1 = first_starter.add_checkpoint_after(first_machine.third_phase)

        second_starter = ProcessStarter(second_machine)
        cp2 = second_starter.add_checkpoint_before(second_machine.first_phase)

        runner = Runner([first_starter, second_starter], [cp1, cp2])

        self.assertIs(next(runner), cp1)
        self.assertEqual(first_machine.steps, [1, 2, 3])
        self.assertEqual(second_machine.steps, [])
        self.assertIs(next(runner), cp2)
        self.assertEqual(second_machine.steps, [1, 2, 3])
