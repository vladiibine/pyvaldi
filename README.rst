===============================
pyvaldi
===============================

| |docs| |travis| |appveyor| |coveralls| |landscape| |scrutinizer|
| |version| |downloads| |wheel| |supported-versions| |supported-implementations|

.. |docs| image:: https://readthedocs.org/projects/pyvaldi/badge/?style=flat
    :target: https://readthedocs.org/projects/pyvaldi
    :alt: Documentation Status

.. |travis| image:: http://img.shields.io/travis/vladiibine/pyvaldi/master.png?style=flat
    :alt: Travis-CI Build Status
    :target: https://travis-ci.org/vladiibine/pyvaldi

.. |appveyor| image:: https://ci.appveyor.com/api/projects/status/github/vladiibine/pyvaldi?branch=master
    :alt: AppVeyor Build Status
    :target: https://ci.appveyor.com/project/vladiibine/pyvaldi

.. |coveralls| image:: http://img.shields.io/coveralls/vladiibine/pyvaldi/master.png?style=flat
    :alt: Coverage Status
    :target: https://coveralls.io/r/vladiibine/pyvaldi

.. |landscape| image:: https://landscape.io/github/vladiibine/pyvaldi/master/landscape.svg?style=flat
    :target: https://landscape.io/github/vladiibine/pyvaldi/master
    :alt: Code Quality Status

.. |version| image:: http://img.shields.io/pypi/v/pyvaldi.png?style=flat
    :alt: PyPI Package latest release
    :target: https://pypi.python.org/pypi/pyvaldi

.. |downloads| image:: http://img.shields.io/pypi/dm/pyvaldi.png?style=flat
    :alt: PyPI Package monthly downloads
    :target: https://pypi.python.org/pypi/pyvaldi

.. |wheel| image:: https://pypip.in/wheel/pyvaldi/badge.png?style=flat
    :alt: PyPI Wheel
    :target: https://pypi.python.org/pypi/pyvaldi

.. |supported-versions| image:: https://pypip.in/py_versions/pyvaldi/badge.png?style=flat
    :alt: Supported versions
    :target: https://pypi.python.org/pypi/pyvaldi

.. |supported-implementations| image:: https://pypip.in/implementation/pyvaldi/badge.png?style=flat
    :alt: Supported imlementations
    :target: https://pypi.python.org/pypi/pyvaldi

.. |scrutinizer| image:: https://img.shields.io/scrutinizer/g/vladiibine/pyvaldi/master.png?style=flat
    :alt: Scrutinizer Status
    :target: https://scrutinizer-ci.com/g/vladiibine/pyvaldi/

Test helper library, for orchestrating parallel processes in order to make assertions about their state

* Free software: MIT license

Introduction
============
This library will help you to test systems that do not have the ideal architecture. 

If you've got a DB server, and multiple other nodes that connect to it, changing state concurrently, you know how annoying it can be to reason about such situations.

While your architecture should of course be improved (if possible), this library makes it easier to make assertions about the state of such a system.

I use 3 concepts for this: **Starters**, **Checkpoints** and **Runners**.

**Starters** are similar to Threads. They will start a certain chain of actions. In other words, they'll get a callable object and call it with some arguments. This callable represents your process under test.

A **checkpoint** represents a snapshot in the life of one of the tested processes. A checkpoint is  considered reached if all actions up to that logical point have been carried out (useful examples: all transactions have been commited OR only started - to test system consistency, all HTTP requests have been sent and responses have been received, or more generally, all methods have been called **UP TO** that point)

A **runner** will run your processes (represented by the starters) in parallel. It must also know the order that the checkpoints should be hit in the life of those processes. It will pause the processes, if necessary, to ensure the checkpoints are hit in exactly the order they should.
When runners pause, you can make assertions about the state of the system (check the DB or any other relevant stateful system). You can then manually resume the runner to either run to the next checkpoint, skip to a specific checkpoint, or to run until all processes have finished.

Of course, I still have to implement this, but this is pretty much a stable form.

Example
=======

Copy-paste from the tests module. This illustrates how 2 processes, running TwoPhaseMachine()() will do so in an orderly fashion. This simulates the scenario when those processes actually run in this order, and we can interrogate their state.

.. code:: python

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


Installation
============

::

    pip install pyvaldi

Documentation
=============

https://pyvaldi.readthedocs.org/

Development
===========

To run the all tests run::

    tox
