# -*- coding: utf-8 -*-
# Copyright (c) 2010-2011 Örjan Persson

"""Argument command for your python program

Easily create commands using the argparse module together. There are two ways
to use it;
- by using a command decorator (recommended)
- automatially registers all commands prefixed with cmd_

The latter requires you to name all functions after a certain pattern (eg. cmd_
and args_). The first is less magic and also recommended.
"""

import argparse
import atexit
import functools
import os
import re
import readline
import sys
import traceback

from gettext import gettext as _

CMD_NAME = 'cmd_'
ARGS_NAMES = ['args_', 'opts_']


def _dir_obj(obj):
    if isinstance(obj, basestring):
        obj = __import__(obj)

    for name in dir(obj):
        if not name.startswith('_'):
            yield name, getattr(obj, name)


def _get_callables(obj, filtered=True):
    return dict((name, attr) for name, attr in _dir_obj(obj)
                             if callable(attr) and
                                (not filtered or not isinstance(attr, command)))


def _get_cmd_name(name):
    if name.startswith(CMD_NAME):
        return name[len(CMD_NAME):]
    else:
        return None


def _get_args_func(cmd_name, callables):
    for args_name in ARGS_NAMES:
        args_cmd = callables.get(args_name + cmd_name)
        if args_cmd:
            return args_cmd


def _get_commands(module):
    # find all who inherits from argcmd
    argcmds = []
    for name, obj in _dir_obj(module):
        try:
            if issubclass(obj, ArgCmd):
                argcmds.append(obj)
                continue
        except:
            pass

    # find all callables and callables for inherited
    callables = _get_callables(module)
    for argcmd in argcmds:
        obj = argcmd()
        obj_callables = _get_callables(obj, False)
        for name, f in obj_callables.items():
            if isinstance(f, command):
                obj_callables.pop(name)

        callables.update(obj_callables)

    # find all cmd_ functions
    for name, func in callables.iteritems():
        cmd_name = _get_cmd_name(name)
        if cmd_name is not None:
            yield func, _get_args_func(cmd_name, callables)


_indent_re = re.compile(r'(\s+)\S')
def _get_doc_lines(cmd_func):
    doc = getattr(cmd_func, '__doc__', None) or '*no documentation*'

    # unindent doc string and construct usage
    doc_lines = doc.splitlines()
    if len(doc_lines) >= 2:
        for n in range(1, len(doc_lines)):
            m = re.match(r'^([ \t]+)', doc_lines[n])
            if m:
                indent_re = re.compile(r'^' + m.group(0))
                for n in range(1, len(doc_lines)):
                    doc_lines[n] = indent_re.sub('', doc_lines[n])
                break

    return doc_lines


class _CommandExecutor(object):
    states = {}

    def __init__(self, func):
        self.func = func

    @classmethod
    def _call_once(cls, obj, func_name):
        if hasattr(obj, 'im_self'):
            states = cls.states.setdefault(func_name, {})
            if obj.im_self not in states:
                states[obj.im_self] = getattr(obj.im_self, func_name)()
            return states[obj.im_self]

    def __call__(self, *args, **kwargs):
        self._call_once(self.func, 'init')
        return self.func(*args, **kwargs)

    def exit(self):
        if hasattr(self.func, 'im_self'):
            states = self.states.get('init')
            if states is not None and self.func.im_self in states:
                return self._call_once(self.func, 'exit')


class command(object):
    """Command argument decorator

    Registers a subcommand function.
    """
    __commands = {}

    def __init__(self, args=None, alias=None):
        self.name = None
        self.func = None
        self.args = args

        if alias and isinstance(alias, basestring):
            alias = [alias]
        self.aliases = alias

    def __call__(self, f, *args, **kwargs):
        if f.func_name in self.__commands:
            raise KeyError('Duplicate command handler: ' + f.func_name)

        cmd = f.func_name.replace(CMD_NAME, '', 1)
        self.name = cmd.replace('_', '-')
        self.func = _CommandExecutor(f)

        self.__name__ = f.__name__

        self.__commands[self.name] = self
        return self

    @classmethod
    def _get_commands(cls):
        return cls.__commands.itervalues()


class _ExtraDecorator(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __call__(self, f, *args, **kwargs):
        if not isinstance(f, command):
            print 'hej', dir(f)
            cmd = command()(f, *args, **kwargs)

            if cmd.args is None:
                callables = _get_callables(f.__module__)
                cmd_name = _get_cmd_name(f.func_name)
                if cmd_name is not None:
                    cmd.args = _get_args_func(cmd_name, callables)
        else:
            cmd = f

        return cmd


class alias(_ExtraDecorator):
    """Command alias decorator

    Adds an alias to a command.

    Arguments:
        alias       -- alias(es) to be added (str or iterable)
    """
    def __call__(self, f, *args, **kwargs):
        cmd = super(argument, self).__call__(f, *args, **kwargs)

        # be lazy and let python handle keyword args etc
        self._add_aliases(cmd, *self.args, **self.kwargs)

        return cmd

    def _add_aliases(self, cmd, alias):
        # combine all aliases and retain order
        if isinstance(alias, basestring):
            alias = [alias]
        if cmd.aliases is None:
            cmd.aliases = []
        cmd.aliases = sum((cmd.aliases, alias), [])


class argument(_ExtraDecorator):
    """Add argument decorator

    See ``argparse`` for syntax. Example:
        @argcmd.argument('-f', '--foobar', ...)
    """
    def __call__(self, f, *args, **kwargs):
        cmd = super(argument, self).__call__(f, *args, **kwargs)

        # chain the old args function together
        def args_wrapper(parser):
            parser.add_argument(*self.args, **self.kwargs)
            if args_wrapper.args is not None:
                args_wrapper.args(parser)

        args_wrapper.args = cmd.args
        cmd.args = args_wrapper

        return cmd


class ArgCmd(object):
    def __new__(cls):
        obj = object.__new__(cls)

        for name, attr in _dir_obj(obj):
            if isinstance(attr, command):
                # for @command decorator for ArgCmd class, there's sometimes no
                # way to reference a function, eg the function is within the
                # same class and the class has not been created -- therefor we
                # allow the callback to be a string. here we transpose the
                # string to a func.
                prev, f = attr, attr.args
                while hasattr(f, 'args'):
                    prev, f = f, f.args
                if isinstance(f, basestring):
                    prev.args = getattr(obj, f)

                # TODO is there a way to fix class functions?
        return obj

    def init(self):
        """Called before first command is run"""
        pass

    def exit(self):
        """Called before exiting

        If run as single command, only called if no exception raised.
        If run in shell, always called.

        Note: This is subject to change."""
        pass


def add_shell_args(parser, prog):
    history_file = '~/.%s-history' % (prog,)
    group = parser.add_argument_group('shell arguments')
    group.add_argument('--history-file', default=history_file, metavar='PATH', help='history [%(default)s]')
    group.add_argument('--enable-history', dest='history', action='store_true', default=False, help='enable command history [%(default)s]')
    group.add_argument('--disable-history', dest='history', action='store_false', help='disable command history')


def run_shell(parser, args):
    """Interactive shell"""
    # TODO add a help command, not just -h
    # parse the argparse not to exit the program
    def exit(status=0, message=None):
        if message:
            parser._print_message(message, sys.stderr)
    parser.exit = exit

    # tokenize command names for partial searching
    # TODO use a real binary tree
    partials = {}
    for cmd in command._get_commands():
        for n in range(len(cmd.name)+1):
            partials.setdefault(cmd.name[0:n],[]).append(cmd.name)
    def complete(text, state):
        matches = partials.get(text)
        if matches and state < len(matches):
            return matches[state]
        else:
            return None

    readline.parse_and_bind('tab: complete')
    readline.set_completer(complete)

    # enable command line history
    if args.history:
        history_path = os.path.expanduser(args.history_file)
        if os.path.exists(history_path):
            readline.read_history_file(history_path)
        def save_history():
            readline.write_history_file(history_path)
        atexit.register(save_history)

    # command line loop
    while True:
        try:
            line = raw_input('>>> ').strip()
        except (EOFError, KeyboardInterrupt):
            print ''
            break
        if line == '':
            continue
        elif line == 'quit':
            break

        try:
            args = parser.parse_args(line.split())
        except:
            continue

        exc, code = _run_command(args.func, args)


def _run_command(func, args):
    try:
        code = func(args)
    except SystemExit, exc:
        return exc, exc.code
    except Exception, exc:
        # TODO make a generic color function
        if args.color:
            prefix, reset = '\x1b[36m', '\x1b[0m'
        else:
            prefix, reset = '', ''

        # TODO write to error stream and format + colorize
        if args.verbosity > 2:
            traceback.print_exc()
        else:
            message = str(exc)
            if not message:
                message = type(exc).__name__
            print 'ERR: %s%s%s' % (prefix, message, reset)

        return exc, 128
    else:
        return None, code


def _setup_parsers(prog):
    parent_parser = argparse.ArgumentParser(prog=prog, add_help=False)
    group = parent_parser.add_argument_group('global arguments')

    # add verbosity
    group.add_argument('-v', '--verbose', action='count', dest='verbosity', default=2, help='increase verbosity')
    group.add_argument('-q', '--quiet', action='store_const', dest='verbosity', const=0, help='be quite')

    # add color
    group.add_argument('--color', action='store_true', default=sys.stdout.isatty(), help='enable colors [%(default)s]')
    group.add_argument('--no-color', action='store_false', dest='color', help='disable colors')

    # add help
    help_parser = argparse.ArgumentParser(prog=prog, add_help=False)
    group = help_parser.add_argument_group('global arguments')
    group.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS, help=_('show this help message and exit'))

    # create two parsers, one just for running the interactive shell and one
    # for running sub-command directly.
    parsers = []
    for parents in ([parent_parser], [help_parser, parent_parser]):
        # TODO make it possible to set description for top level
        formatter_class = argparse.RawDescriptionHelpFormatter
        parser = argparse.ArgumentParser(prog=prog, parents=parents,
                                         formatter_class=formatter_class,
                                         add_help=False)
        parsers.append(parser)

    # setup the 2nd parser for sub-command
    subparsers = parser.add_subparsers(dest='subparser_name')

    # setup the parser for all commands
    for cmd in command._get_commands():
        doc_lines = _get_doc_lines(cmd.func.func)

        help = doc_lines[0]
        desc = '\n'.join(doc_lines[1:])

        cmd_parser = subparsers.add_parser(cmd.name, parents=parents,
                                           formatter_class=formatter_class,
                                           help=help, add_help=False,
                                           description=desc)
        cmd_parser.set_defaults(func=cmd.func)

        # call the commands args callback for populating it's arguments
        if callable(cmd.args):
            cmd.args(cmd_parser)

    return parsers


def main(module='__main__', prog=None, shell=False):
    """Main entrance for a program

    Call this function in your file to automatically populate an argument
    parser and register all your cmd-functions.
    """
    # automatically populate commands found in module
    if module is not None:
        for cmd_func, cmd_args in _get_commands(module):
            command(args=cmd_args)(cmd_func)

    shell_parser, parser = _setup_parsers(prog)
    func = None

    # first try to parse the command line for missing sub-command
    if shell:
        # make the parser not to exit the program in case of parse error
        def exit(*args, **kwargs):
            exit.error = True
        shell_parser.error = exit
        shell_parser.exit = exit

        # XXX remove these args completley?
        #add_shell_args(parser, shell_parser.prog)
        add_shell_args(shell_parser, shell_parser.prog)

        # if successfully parsed, let's start the interactive shell
        args = shell_parser.parse_args()
        if not hasattr(exit, 'error'):
            func = functools.partial(run_shell, parser)

    # run main parser to see if it's a single run sub-command
    if not func:
        args = parser.parse_args()
        func = args.func

    # run the command and send exit if successful
    exc, code = _run_command(func, args)
    if exc is None:
        for cmd in command._get_commands():
            cmd.func.exit()

    parser.exit(code)
