import unittest

from pyvaldi import (ProcessPlayer, ProcessConductor, Baton, Checkpoint,
                     ImplicitCheckpoint)
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


class BatonCheckpointOrderTestCase(unittest.TestCase):
    def test_empty_checkpoint_list_yields_empty_player_order(self):
        baton = Baton([])

        assert baton.checkpoint_order == []

    def test_single_checkpoint_generates_single_player_list(self):
        player = ProcessPlayer(None)
        baton = Baton([Checkpoint(player, 1)])

        order = [cp.player for cp in baton.checkpoint_order]
        assert order == [player] * 3

    def test_multiple_checkpoints_single_player(self):
        player = ProcessPlayer(None)
        baton = Baton([Checkpoint(player, 1), Checkpoint(player, 2)])

        order = [cp.player for cp in baton.checkpoint_order]
        assert order == [player] * 4

    def test_2_players_each_with_1_checkpoint(self):
        player1 = ProcessPlayer(None, name='p1')
        player2 = ProcessPlayer(None, name='p2')

        baton = Baton([Checkpoint(player1, 0), Checkpoint(player2, 0)])

        order = [cp.player for cp in baton.checkpoint_order]
        assert order == [player1] * 3 + [player2] * 3

    def test_2_players_with_2_and_1_checkpoint_respectively_non_mixed(self):
        player1 = ProcessPlayer(None, name='p1')
        player2 = ProcessPlayer(None, name='p2')

        baton = Baton([
            Checkpoint(player1, 0), Checkpoint(player1, 0),
            Checkpoint(player2, 0)]
        )

        order = [cp.player for cp in baton.checkpoint_order]
        assert order == [player1] * 4 + [player2] * 3

    def test_2_players_with_multiple_checkpoints_mixed(self):
        p1 = ProcessPlayer(None, name='p1')
        p2 = ProcessPlayer(None, name='p2')

        baton = Baton([
            Checkpoint(p1, 0), Checkpoint(p2, 0),
            Checkpoint(p1, 0), Checkpoint(p2, 0)
        ])

        order = [cp.player for cp in baton.checkpoint_order]
        assert order == [p1] * 2 + [p2] * 2 + [p1] * 2 + [p2] * 2

    def test_4_players_with_multiple_checkpoints_mixed(self):
        p1 = ProcessPlayer(None, name='p1')
        p2 = ProcessPlayer(None, name='p2')
        p3 = ProcessPlayer(None, name='p3')
        p4 = ProcessPlayer(None, name='p4')
        
        CP = Checkpoint
        baton = Baton([CP(p1, 0), CP(p2, 0), CP(p3, 0), CP(p4, 0)] * 3)

        order = [cp.player for cp in baton.checkpoint_order]
        assert order == (
            [p1] * 2 + [p2] * 2 + [p3] * 2 + [p4] * 2 +
            [p1] * 1 + [p2] * 1 + [p3] * 1 + [p4] * 1 +
            [p1] * 2 + [p2] * 2 + [p3] * 2 + [p4] * 2
        )
