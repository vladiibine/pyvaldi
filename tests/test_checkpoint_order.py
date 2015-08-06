import unittest

from pyvaldi import (ProcessStarter, Runner, generate_checkpoint_pairs,
                     NULL_CHECKPOINT)
from .artefacts import ThreePhaseMachine


class TwoThreadsTestCase(unittest.TestCase):

    def test_checkpoint_order_simple_2_procs_3_checkpoints_each(self):
        # Time -> ...
        # Process 1: CP1   CP2   CP3
        # Process 2:                      CP1   CP2   CP3
        machine1 = ThreePhaseMachine()
        machine2 = ThreePhaseMachine()

        starter1 = ProcessStarter(machine1)
        starter2 = ProcessStarter(machine2)

        cp1_1 = starter1.add_checkpoint_before(machine1.first_phase)
        cp1_2 = starter1.add_checkpoint_before(machine1.second_phase)
        cp1_3 = starter1.add_checkpoint_before(machine1.third_phase)

        cp2_1 = starter2.add_checkpoint_before(machine2.first_phase)
        cp2_2 = starter2.add_checkpoint_before(machine2.second_phase)
        cp2_3 = starter2.add_checkpoint_before(machine2.third_phase)

        runner = Runner(
            [starter1, starter2],
            [cp1_1, cp1_2, cp1_3, cp2_1, cp2_2, cp2_3])

        self.assertIs(next(runner), cp1_1)
        self.assertIs(next(runner), cp1_2)
        self.assertIs(next(runner), cp1_3)
        self.assertIs(next(runner), cp2_1)
        self.assertIs(next(runner), cp2_2)
        self.assertIs(next(runner), cp2_3)

    def test_checkpoint_order_mixed_2_procs_3_checkpoints_each(self):
        # Time -> ... (checkpoints order)
        # Process 1:  CP1      CP2   CP3
        # Process 2:      CP1             CP2 CP3
        machine1 = ThreePhaseMachine()
        machine2 = ThreePhaseMachine()

        starter1 = ProcessStarter(machine1)
        starter2 = ProcessStarter(machine2)

        cp1_1 = starter1.add_checkpoint_before(machine1.first_phase)
        cp1_2 = starter1.add_checkpoint_before(machine1.second_phase)
        cp1_3 = starter1.add_checkpoint_before(machine1.third_phase)

        cp2_1 = starter2.add_checkpoint_before(machine2.first_phase)
        cp2_2 = starter2.add_checkpoint_before(machine2.second_phase)
        cp2_3 = starter2.add_checkpoint_before(machine2.third_phase)

        runner = Runner(
            [starter1, starter2],
            [cp1_1, cp2_1, cp1_2, cp1_3, cp2_2, cp2_3])

        self.assertIs(next(runner), cp1_1)
        self.assertIs(next(runner), cp2_1)
        self.assertIs(next(runner), cp1_2)
        self.assertIs(next(runner), cp1_3)
        self.assertIs(next(runner), cp2_2)
        self.assertIs(next(runner), cp2_3)


class ThreadSwitchingTestCase(unittest.TestCase):
    """Test what happens when you switch threads """
    def test_switching_when_not_done_with_previous_thread_initial_yielded(self):
        # switching from 1 to 2, but we're not done with 1
        # p1:  1          2         TERM
        # p2:     INIT 1            TERM
        # last = p1c2; next = p2c1
            # return p2.cp1, p2.INITIAL
        machine1 = ThreePhaseMachine()
        machine2 = ThreePhaseMachine()

        starter1 = ProcessStarter(machine1)
        starter2 = ProcessStarter(machine2)

        proc1_cp1 = starter1.add_checkpoint_after(machine1.first_phase)
        proc2_cp1 = starter2.add_checkpoint_after(machine2.second_phase)
        proc1_cp2 = starter1.add_checkpoint_after(machine1.third_phase)
        checkpoints = [proc1_cp1, proc2_cp1, proc1_cp2]

        results = list(generate_checkpoint_pairs(checkpoints, 1))

        proc2_initial = starter2.get_initial_checkpoint()

        self.assertEqual(results, [(proc2_cp1, proc2_initial)])

    def test_switching_when_done_with_previous_thread_terminal_yielded(self):
        # switching from 1 to 2, and we're done with 1 - will insert
        # the terminal node for process 1 before switching
        # p1: 1         ..TERM
        # p2:      1    ..TERM
        machine1 = ThreePhaseMachine()
        machine2 = ThreePhaseMachine()

        starter1 = ProcessStarter(machine1)
        starter2 = ProcessStarter(machine2)

        proc1_cp1 = starter1.add_checkpoint_after(machine1.first_phase)
        proc2_cp1 = starter2.add_checkpoint_after(machine2.first_phase)

        checkpoints = [proc1_cp1, proc2_cp1]

        results = list(generate_checkpoint_pairs(checkpoints, 1))

        self.assertEqual(
            results,
            [(starter1.get_terminal_checkpoint(), proc1_cp1),
             (proc2_cp1, starter2.get_initial_checkpoint())]
        )


class SingleThreadTestCase(unittest.TestCase):
    def test_single_checkpoint_is_returned_by_runner(self):
        machine = ThreePhaseMachine()

        starter = ProcessStarter(machine)
        cp1 = starter.add_checkpoint_before(machine.first_phase)
        runner = Runner([starter], [cp1])

        self.assertIs(next(runner), cp1)

    def test_3_checkpoints_are_returned_by_runner(self):
        machine = ThreePhaseMachine()

        starter = ProcessStarter(machine)
        cp1 = starter.add_checkpoint_before(machine.first_phase, '1-1')
        cp2 = starter.add_checkpoint_before(machine.second_phase, '1-2')
        cp3 = starter.add_checkpoint_before(machine.third_phase, '1-3')

        runner = Runner([starter], [cp1, cp2, cp3])

        self.assertIs(next(runner), cp1)
        self.assertIs(next(runner), cp2)
        self.assertIs(next(runner), cp3)


class ImplicitCheckpointInterpolatorTestCase(unittest.TestCase):
    pass
