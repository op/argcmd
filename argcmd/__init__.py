# -*- coding: utf-8 -*-
# Copyright (c) 2010 Örjan Persson

"""Argument command for your python program

Easily create commands using the argparse module together. Automatially
registers all commands prefixed with cmd_. You can add arguments to the command
by adding a matching opts_-function.
"""

import argparse
import re
import sys


def _get_commands(_globals):
    for name, value in _globals.items():
        if name.startswith('cmd_') and callable(value):
            cmd = name.replace('cmd_', '', 1)
            opts_cmd = _globals.get('opts_' + cmd)
            yield cmd.replace('_', '-'), value, opts_cmd


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


def main(_globals):
    """Main entrance for a program

    Call this function in your file to automatically populate an argument
    parser and register all your cmd-functions.
    """
    # TODO make it possible to set description for top level
    formatter_class = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(formatter_class=formatter_class)
    subparsers = parser.add_subparsers()

    for cmd, cmd_func, cmd_opts in _get_commands(_globals):
        doc_lines = _get_doc_lines(cmd_func)

        help = doc_lines[0]
        desc = '\n'.join(doc_lines[1:])

        cmd_parser = subparsers.add_parser(cmd, help=help, description=desc,
                                           formatter_class=formatter_class)
        cmd_parser.set_defaults(func=cmd_func)

        # automatically call any opts_<func-name> to make it possible to
        # populate the subparser with arguments
        if cmd_opts:
            cmd_opts(cmd_parser)

    args = parser.parse_args()
    sys.exit(args.func(args))
