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

    def test_run_to_first_checkpoint_before_method(self):
        machine = ThreePhaseMachine()
        starter = ProcessStarter(machine)
        cp = starter.add_checkpoint_before(machine.third_phase)

        runner = Runner([starter], [cp])

        next(runner)
        self.assertEqual(machine.steps, [1, 2])

    def test_run_to_first_checkpoint_after_method(self):
        machine = ThreePhaseMachine()
        starter = ProcessStarter(machine)
        cp = starter.add_checkpoint_after(machine.second_phase)

        runner = Runner([starter], [cp])

        next(runner)
        self.assertEqual(machine.steps, [1, 2])

    def test_second_checkpoint_is_reached(self):
        machine = ThreePhaseMachine()
        starter = ProcessStarter(machine)

        cp1 = starter.add_checkpoint_before(machine.second_phase)
        cp2 = starter.add_checkpoint_before(machine.third_phase)

        runner = Runner([starter], [cp1, cp2])

        next(runner)
        self.assertEqual(machine.steps, [1])
        next(runner)
        self.assertEqual(machine.steps, [1, 2])

    def test_continue_until_the_end(self):
        machine = ThreePhaseMachine()
        starter = ProcessStarter(machine)

        cp1 = starter.add_checkpoint_before(machine.third_phase)

        runner = Runner([starter], [cp1])
        next(runner)
        next(runner)

        self.assertEqual(machine.steps, [1, 2, 3])


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
        next(runner)
        self.assertEqual(second_machine.steps, [1, 2, 3])

    def test_simple_order_for_2_processes(self):
        # Time -> ...
        # Process 1: CP1   CP2   CP3
        # Process 2:                      CP1   CP2   CP3
        machine1 = ThreePhaseMachine()
        machine2 = ThreePhaseMachine()
        starter1 = ProcessStarter(machine1)
        starter2 = ProcessStarter(machine2)

        cp1_1 = starter1.add_checkpoint_before(machine1.first_phase)
        cp1_2 = starter1.add_checkpoint_before(machine1.second_phase)
        cp1_3 = starter1.add_checkpoint_after(machine1.third_phase)

        cp2_1 = starter2.add_checkpoint_before(machine2.first_phase)
        cp2_2 = starter2.add_checkpoint_before(machine2.second_phase)
        cp2_3 = starter2.add_checkpoint_before(machine2.third_phase)

        runner = Runner(
            [starter1, starter2],
            [cp1_1, cp1_2, cp1_3, cp2_1, cp2_2, cp2_3]
        )

        next(runner)
        self.assertEqual(machine1.steps, [])
        next(runner)
        self.assertEqual(machine1.steps, [1])
        next(runner)
        self.assertEqual(machine1.steps, [1, 2, 3])
        next(runner)
        self.assertEqual(machine2.steps, [])
        self.assertEqual(machine1.steps, [1, 2, 3])
        next(runner)
        self.assertEqual(machine2.steps, [1])
        next(runner)
        self.assertEqual(machine2.steps, [1, 2])
        next(runner)
        self.assertEqual(machine2.steps, [1, 2, 3])

    def test_when_switching_threads_all_are_run_until_the_end(self):
        # Time -> ...
        # Process 1: CP1   CP2   CP3
        # Process 2:                      CP1   CP2   CP3
        machine1 = ThreePhaseMachine()
        machine2 = ThreePhaseMachine()
        starter1 = ProcessStarter(machine1)
        starter2 = ProcessStarter(machine2)

        cp1_1 = starter1.add_checkpoint_before(machine1.third_phase)

        cp2_1 = starter2.add_checkpoint_before(machine2.third_phase)

        runner = Runner([starter1, starter2], [cp1_1, cp2_1])

        next(runner)
        next(runner)
        self.assertEqual(machine2.steps, [1, 2])
        # Easy enough to fix: need special checkpoints that mark that the
        # thread has exited BUT we also need to make a decision in this
        # special non-explicit case. Let's just let the currently running
        # thread to continue
        self.assertEqual(machine1.steps, [1, 2, 3])
