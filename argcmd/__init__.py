# -*- coding: utf-8 -*-
# Copyright (c) 2010-2011 Örjan Persson

"""Argument command for your python program

Easily create commands using the argparse module together. There are two ways
to use it;
- by using a command decorator (recommended)
- automatially registers all commands prefixed with cmd_

The latter requires you to pass globals() into the argcmd.main-function,
requires you to name all functions after a certain pattern (eg. cmd_ and
args_). The first is less magic and also recommended.
"""

import argparse
import re
import sys

CMD_NAME = 'cmd_'
ARGS_NAMES = ['args_', 'opts_']

def _get_commands(module):
    # collect all callables
    callables = {}
    for name in dir(module):
        obj = getattr(module, name)
        if callable(obj):
            callables[name] = obj

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
        self.func = f

        self.__commands[self.name] = self
        return None

    @classmethod
    def _get_commands(cls):
        return cls.__commands.itervalues()


def main(module='__main__'):
    """Main entrance for a program

    Call this function in your file to automatically populate an argument
    parser and register all your cmd-functions.
    """
    parent_parser = argparse.ArgumentParser(add_help=False)
    group = parent_parser.add_argument_group('global arguments')

    # add verbosity
    group.add_argument('-v', '--verbose', action='count', dest='verbosity', default=2, help='increase verbosity')
    group.add_argument('-q', '--quiet', action='store_const', dest='verbosity', const=0, help='be quite')

    # add color
    group.add_argument('--color', action='store_true', default=sys.stdout.isatty(), help='enable colors [%(default)s]')
    group.add_argument('--no-color', action='store_false', dest='color', help='disable colors')

    # TODO make it possible to set description for top level
    formatter_class = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(parents=[parent_parser],
                                     formatter_class=formatter_class)

    subparsers = parser.add_subparsers()

    # automatically populate commands found in module
    if isinstance(module, basestring):
        module = __import__(module)
    for cmd_func, cmd_args in _get_commands(module):
        command(args=cmd_args)(cmd_func)

    # setup the parser for all commands
    for cmd in command._get_commands():
        doc_lines = _get_doc_lines(cmd.func)

        help = doc_lines[0]
        desc = '\n'.join(doc_lines[1:])

        cmd_parser = subparsers.add_parser(cmd.name, parents=[parent_parser],
                                           formatter_class=formatter_class,
                                           help=help, description=desc)
        cmd_parser.set_defaults(func=cmd.func)

        # call the commands args callback for populating it's arguments
        if callable(cmd.args):
            cmd.args(cmd_parser)

    args = parser.parse_args()
    sys.exit(args.func(args))
