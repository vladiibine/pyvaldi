import unittest

from pyvaldi import (ProcessPlayer, ProcessConductor,
                     NULL_CHECKPOINT, ImplicitCheckpoint)
from .artefacts import ThreePhaseMachine


class TwoThreadsTestCase(unittest.TestCase):

    def test_checkpoint_order_simple_2_procs_3_checkpoints_each(self):
        # Time -> ...
        # Process 1: CP1   CP2   CP3
        # Process 2:                      CP1   CP2   CP3
        machine1 = ThreePhaseMachine()
        machine2 = ThreePhaseMachine()

        starter1 = ProcessPlayer(machine1)
        starter2 = ProcessPlayer(machine2)

        cp1_1 = starter1.add_checkpoint_before(machine1.first_phase)
        cp1_2 = starter1.add_checkpoint_before(machine1.second_phase)
        cp1_3 = starter1.add_checkpoint_before(machine1.third_phase)

        cp2_1 = starter2.add_checkpoint_before(machine2.first_phase)
        cp2_2 = starter2.add_checkpoint_before(machine2.second_phase)
        cp2_3 = starter2.add_checkpoint_before(machine2.third_phase)

        runner = ProcessConductor(
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

        starter1 = ProcessPlayer(machine1, 's1')
        starter2 = ProcessPlayer(machine2, 's2')

        cp1_1 = starter1.add_checkpoint_before(machine1.first_phase, '1')
        cp1_2 = starter1.add_checkpoint_before(machine1.second_phase, '2')
        cp1_3 = starter1.add_checkpoint_before(machine1.third_phase, '3')

        cp2_1 = starter2.add_checkpoint_before(machine2.first_phase, '1')
        cp2_2 = starter2.add_checkpoint_before(machine2.second_phase, '2')
        cp2_3 = starter2.add_checkpoint_before(machine2.third_phase, '3')

        runner = ProcessConductor(
            [starter1, starter2],
            [cp1_1, cp2_1, cp1_2, cp1_3, cp2_2, cp2_3])

        self.assertIs(next(runner), cp1_1)
        self.assertIs(next(runner), cp2_1)
        self.assertIs(next(runner), cp1_2)
        self.assertIs(next(runner), cp1_3)
        self.assertIs(next(runner), cp2_2)
        self.assertIs(next(runner), cp2_3)


class SingleThreadTestCase(unittest.TestCase):
    def test_single_checkpoint_is_returned_by_runner(self):
        machine = ThreePhaseMachine()

        starter = ProcessPlayer(machine)
        cp1 = starter.add_checkpoint_before(machine.first_phase)
        runner = ProcessConductor([starter], [cp1])

        self.assertIs(next(runner), cp1)

    def test_3_checkpoints_are_returned_by_runner(self):
        machine = ThreePhaseMachine()

        starter = ProcessPlayer(machine)
        cp1 = starter.add_checkpoint_before(machine.first_phase, '1-1')
        cp2 = starter.add_checkpoint_before(machine.second_phase, '1-2')
        cp3 = starter.add_checkpoint_before(machine.third_phase, '1-3')

        runner = ProcessConductor([starter], [cp1, cp2, cp3])

        self.assertIs(next(runner), cp1)
        self.assertIs(next(runner), cp2)
        self.assertIs(next(runner), cp3)



