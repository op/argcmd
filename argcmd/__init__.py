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

from gettext import gettext as _

CMD_NAME = 'cmd_'
ARGS_NAMES = ['args_', 'opts_']


def _get_commands(module):
    # collect all callables and argcommands
    argcmds, callables = [], {}
    for name in dir(module):
        if name.startswith('_'):
            continue
        obj = getattr(module, name)
        try:
            if issubclass(obj, ArgCommand):
                argcmds.append(obj)
                continue
        except:
            if callable(obj):
                callables[name] = obj
                continue

    # find all callables for the class
    for argcmd in argcmds:
        obj = argcmd()
        for name in dir(obj):
            if name.startswith('_'):
                continue
            f = getattr(obj, name)
            if isinstance(f, command):
                # transpose function string name
                if isinstance(f.args, basestring):
                    f.args = getattr(obj, f.args)
            elif callable(f):
                callables[name] = f

    # find all cmd_ functions
    for name, func in callables.iteritems():
        if name.startswith(CMD_NAME):
            cmd = name.replace(CMD_NAME, '', 1)
            # find matching args_ function
            for args_name in ARGS_NAMES:
                args_cmd = callables.get(args_name + cmd)
                if args_cmd:
                    break
            yield func, args_cmd


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

    def __init__(self, args=None):
        self.name = None
        self.func = None
        self.args = args

    def __call__(self, f, *args, **kwargs):
        if f.func_name in self.__commands:
            raise KeyError('Duplicate command handler: ' + f.func_name)

        cmd = f.func_name.replace(CMD_NAME, '', 1)
        self.name = cmd.replace('_', '-')
        self.func = _CommandExecutor(f)

        self.__commands[self.name] = self
        return self

    @classmethod
    def _get_commands(cls):
        return cls.__commands.itervalues()


class ArgCommand(object):
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
        message = str(exc)
        if message == '':
            message = exc.__class__.__name__
        # TODO make a generic color function
        if args.color:
            prefix, reset = '\x1b[33m', '\x1b[0m'
        else:
            prefix, reset = '', ''
        if args.verbosity > 2:
            print 'ERRR verbost:', prefix, message, reset
        else:
            print 'ERR:', prefix, message, reset
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
    if isinstance(module, basestring):
        module = __import__(module)

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
