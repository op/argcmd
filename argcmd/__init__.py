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

# TODO
# - add a help command, not just -h
# - add colorize function
# - add logging
# - beatify errors
# - check cmd module out

import argparse
import atexit
import functools
import os
import re
import readline
import sys
import traceback

from gettext import gettext as _

# prefix for functions to find automatic
CMD_NAME = 'cmd_'
ARGS_NAMES = ['arg_', 'args_', 'opts_']

# error exit codes
RC_OK = 0
RC_CMD_ERROR = 128
RC_PARSE_ERROR = 2


class ArgParseError(Exception):
    def __init__(self, status, error):
        self.status = status
        self.error = error


class _AliasedSubParsersAction(argparse._SubParsersAction):
    def add_parser(self, name, **kwargs):
        aliases = kwargs.pop('aliases', ())
        for alias in aliases:
            self.choices[alias] = name
        return super(_AliasedSubParsersAction, self).add_parser(name, **kwargs)

    def __call__(self, parser, namespace, values, *args, **kwargs):
        # translate aliased call to real name
        choice = self.choices.get(values[0])
        if isinstance(choice, basestring):
            values = [choice] + values[1:]
        sup = super(_AliasedSubParsersAction, self)
        return sup.__call__(parser, namespace, values, *args, **kwargs)


def _dir_obj(obj):
    if isinstance(obj, basestring):
        obj = __import__(obj)

    if isinstance(obj, dict):
        for key, value in obj.iteritems():
            yield key, value
    else:
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
                command._setup_command(obj, f)

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
    """Function executor

    Makes sure to call certain functions on an object before first call to
    that objects function. If the object has been setup, it will also make
    sure to call tear down.
    """
    states = {}

    __setup_func = 'init'
    __teardown_func = 'exit'

    def __init__(self, func):
        self.func = func

    def __repr__(self):
        return '%s(func=%s)' % (self.__class__.__name__, self.func)

    @classmethod
    def _call_once(cls, obj, func_name):
        if hasattr(obj, 'im_self'):
            states = cls.states.setdefault(func_name, {})
            if obj.im_self not in states:
                states[obj.im_self] = getattr(obj.im_self, func_name)()
            return states[obj.im_self]

    def __call__(self, *args, **kwargs):
        self._call_once(self.func, self.__setup_func)
        return self.func(*args, **kwargs)

    def exit(self):
        if hasattr(self.func, 'im_self'):
            states = self.states.get(self.__setup_func)
            if states is not None and self.func.im_self in states:
                return self._call_once(self.func, self.__teardown_func)


class command(object):
    """Command argument decorator

    Registers a subcommand function.
    """
    __commands = {}

    @classmethod
    def _get_commands(cls):
        return cls.__commands.itervalues()

    @classmethod
    def _slugify(cls, f):
        name = f.func_name.replace(CMD_NAME, '', 1)
        return name.replace('_', '-')

    @classmethod
    def _setup_command(cls, obj, f):
        # FIXME we shouldn't need to do this. the problem occurs when adding
        # a decorator to a method of ArgCmd subclass. the __call__ below will
        # occur before any object exists, hence the registered function will be
        # missing a proper self object. this is a quick fix to add self to it.
        f.func.func = functools.partial(f.temp, obj)
        f.func.func.__doc__ = f.temp.__doc__

    @classmethod
    def _reset(cls):
        cls.__commands = {}

    def __init__(self, args=None, alias=None):
        self.name = None
        self.func = None
        self.args = args

        if alias and isinstance(alias, basestring):
            alias = [alias]
        self.aliases = alias

    def __call__(self, *args, **kwargs):
        if self.func is None:
            return self._register_command(*args, **kwargs)
        else:
            return self.func(*args, **kwargs)

    def _register_command(self, f):
        assert f is not None, 'Invalid function'

        self.name = self._slugify(f)
        self.func = _CommandExecutor(f)
        self.temp = f

        # XXX needed?
        self.__name__ = f.__name__

        if self.name in self.__commands:
            raise KeyError('Duplicate command handler: ' + f.func_name)

        self.__commands[self.name] = self
        return self

    def _add_arguments(self, parser):
        if callable(self.args):
            self.args(parser)


class _ExtraDecorator(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __call__(self, f, *args, **kwargs):
        if not isinstance(f, command):
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
        cmd = super(alias, self).__call__(f, *args, **kwargs)

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
    # XXX make this configurable
    history_file = '~/.%s-history' % (prog,)
    group = parser.add_argument_group('shell arguments')
    group.add_argument('--history-file', default=history_file, metavar='PATH', help='history [%(default)s]')
    group.add_argument('--enable-history', dest='history', action='store_true', default=False, help='enable command history [%(default)s]')
    group.add_argument('--disable-history', dest='history', action='store_false', help='disable command history')


def run_shell(parser, args):
    """Interactive shell"""
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
        except ArgParseError, exc:
            # TODO see below on next ArgParseError
            if exc.status:
                sys.stderr.write('%s: error: %s\n' % (parser.prog, exc.error))
        except:
            # TODO
            raise
        else:
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
            sys.stdout.write('ERR: %s%s%s\n' % (prefix, message, reset))

        return exc, RC_CMD_ERROR
    else:
        if code is None:
            code = RC_OK
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

    def patch_parser(parser):
        # patch the argparse parser not to exit the program on error
        def exit(status=RC_OK, message=None):
            raise ArgParseError(status, message)
        parser.exit = exit
        parser.error = functools.partial(exit, RC_PARSE_ERROR)

    # create two parsers, one just for running the interactive shell and one
    # for running sub-command directly.
    parsers = []
    for parents in ([parent_parser], [help_parser, parent_parser]):
        # TODO make it possible to set description for top level
        formatter_class = argparse.RawDescriptionHelpFormatter
        parser = argparse.ArgumentParser(prog=prog, parents=parents,
                                         formatter_class=formatter_class,
                                         add_help=False)
        parser.register('action', 'parsers', _AliasedSubParsersAction)

        patch_parser(parser)
        parsers.append(parser)

    # setup the 2nd parser for sub-command
    subparsers = parser.add_subparsers(dest='subparser_name')
    patch_parser(subparsers)

    # setup the parser for all commands
    for cmd in command._get_commands():
        doc_lines = _get_doc_lines(cmd.func.func)

        help = doc_lines[0]
        desc = '\n'.join(doc_lines[1:])

        cmd_parser = subparsers.add_parser(cmd.name, parents=parents,
                                           formatter_class=formatter_class,
                                           help=help, add_help=False,
                                           aliases=cmd.aliases or (),
                                           description=desc)
        patch_parser(cmd_parser)

        cmd_parser.set_defaults(func=cmd)
        cmd._add_arguments(cmd_parser)

    return parsers


def main(module='__main__', prog=None, shell=False, args=None):
    """Main entrance for a program

    Call this function in your file to automatically populate an argument
    parser and register all your cmd-functions.

    By default, `module` is set to search from where the execution started.
    The value can either be the name of a module, an already imported module
    or a dictionary (similar to what `globals()` and ``locals()``.)

    Keyword arguments:
        `module`        -- where to automatically search for commands
        `prog`          -- name of the program
        `shell`         -- include interactive shell, disabled by default
        `args`          -- arguments to parse (defaults to sys.argv[1:])
    """
    # automatically populate commands found in module
    if module is not None:
        for cmd_func, cmd_args in _get_commands(module):
            command(args=cmd_args)(cmd_func)

    shell_parser, parser = _setup_parsers(prog)
    func = None

    if args is None:
        args = sys.argv[1:]

    # first try to parse the command line for missing sub-command
    if shell:
        # XXX remove these args completley?
        #add_shell_args(parser, shell_parser.prog)
        add_shell_args(shell_parser, shell_parser.prog)

        # if successfully parsed, let's start the interactive shell
        # XXX rework this to look for an optional sub-command if possible
        try:
            cmd_args = shell_parser.parse_args(args)
            func = functools.partial(run_shell, parser)
        except ArgParseError:
            pass

    # run main parser to see if it's a single run sub-command
    if not func:
        try:
            cmd_args = parser.parse_args(args)
            func = cmd_args.func
        except ArgParseError, exc:
            if exc.status:
                # TODO clean this up and try to use the real error function found
                # in the argparse package (it's patched away, so this mimics it)
                sys.stderr.write(parser.format_usage())
                sys.stderr.write('%s: error: %s\n' % (parser.prog, exc.error))
            return sys.exit(exc.status)

    # run the command and send exit if successful
    exc, code = _run_command(func, cmd_args)
    if exc is None:
        for cmd in command._get_commands():
            cmd.func.exit()

    return sys.exit(code)
