#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2011 Örjan Persson

import mock
import unittest

import argcmd


class TestCase(unittest.TestCase):
    def setUp(self):
        self.reset = argcmd.command._reset
        self.reset()


class CommandExecutorTest(TestCase):

    # TODO replace with mock when internet is available
    class TestCommand(argcmd.ArgCmd):
        def __init__(self):
            for name in ['foo', 'bar', 'start', 'stop']:
                func = mock.Mock(spec=['__name__', 'func_name'])
                setattr(func, '__name__', name)
                setattr(func, 'func_name', name)
                setattr(self, name, func)

    def test_call_once(self):
        cmd = self.TestCommand()

        # just validate that the mock works
        self.assertEquals(cmd.foo.call_count, 0)
        cmd.foo()
        self.assertEquals(cmd.foo.call_count, 1)

        exc = argcmd._CommandExecutor(cmd.foo)
        self.assertEquals(cmd.start.call_count, 0)
        self.assertEquals(cmd.stop.call_count, 0)
        self.assertEquals(cmd.foo.call_count, 1)

        exc(cmd)
        self.assertEquals(cmd.start.call_count, 1)
        self.assertEquals(cmd.stop.call_count, 0)
        self.assertEquals(cmd.foo.call_count, 2)

        exc.tear_down(cmd)
        self.assertEquals(cmd.start.call_count, 1)
        self.assertEquals(cmd.stop.call_count, 1)
        self.assertEquals(cmd.foo.call_count, 2)

    def test_command(self):
        t_cmd = self.TestCommand()
        argcmd.command._add_command(t_cmd, t_cmd.foo)
        argcmd.command._add_command(t_cmd, t_cmd.bar)
        commands = dict(((c.name, c) for c in argcmd.command._get_commands()))

        cmd = commands['foo']

        self.assertEquals(t_cmd.start.call_count, 0)
        self.assertEquals(t_cmd.stop.call_count, 0)
        self.assertEquals(t_cmd.foo.call_count, 0)
        self.assertEquals(t_cmd.bar.call_count, 0)

        cmd.execute()
        self.assertEquals(t_cmd.start.call_count, 1)
        self.assertEquals(t_cmd.stop.call_count, 0)
        self.assertEquals(t_cmd.foo.call_count, 1)
        self.assertEquals(t_cmd.bar.call_count, 0)

        cmd.execute()
        self.assertEquals(t_cmd.start.call_count, 1)
        self.assertEquals(t_cmd.stop.call_count, 0)
        self.assertEquals(t_cmd.foo.call_count, 2)
        self.assertEquals(t_cmd.bar.call_count, 0)

        cmd = commands['bar']

        cmd.execute()
        self.assertEquals(t_cmd.start.call_count, 1)
        self.assertEquals(t_cmd.stop.call_count, 0)
        self.assertEquals(t_cmd.foo.call_count, 2)
        self.assertEquals(t_cmd.bar.call_count, 1)

        argcmd.command.tear_down()
        self.assertEquals(t_cmd.start.call_count, 1)
        self.assertEquals(t_cmd.stop.call_count, 1)
        self.assertEquals(t_cmd.foo.call_count, 2)
        self.assertEquals(t_cmd.bar.call_count, 1)


class CommandTest(TestCase):
    @mock.patch('sys.exit')
    def test_register_functions(self, mock_exit):
        def cmd_foo(args):
            return 'test_register_functions'
        argcmd.main(module=locals(), args=['foo'])
        mock_exit.assert_called_with('test_register_functions')

        self.reset()
        argcmd.main(module=locals(), args=['bar'])
        mock_exit.assert_called_with(2)

    @mock.patch('sys.exit')
    def test_register_decorator(self, mock_exit):
        class Test(argcmd.ArgCmd):
            @argcmd.command()
            def foo(self, args):
                return 'test_register_decorator'

        argcmd.main(module=locals(), args=['foo'])
        mock_exit.assert_called_with('test_register_decorator')

    @mock.patch('sys.exit')
    def test_register_function_name(self, mock_exit):
        class Test(argcmd.ArgCmd):
            def cmd_foo(self, args):
                return 'register_function_name'

        argcmd.main(module=locals(), args=['foo'], shell=False)
        mock_exit.assert_called_with('register_function_name')

        self.reset()
        argcmd.main(module=locals(), args=['foo'], shell=True)
        mock_exit.assert_called_with('register_function_name')

    @mock.patch('sys.exit')
    def test_register_duplicate(self, mock_exit):
        class Test(argcmd.ArgCmd):
            @argcmd.command()
            def foo(self, args):
                pass
            def cmd_foo(self, args):
                pass
        self.assertRaises(KeyError, argcmd.main, module=locals())


if __name__ == '__main__':
    unittest.main()
