#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argcmd


def some_crazy_name(parser):
    parser.add_argument('-a', '--arg', default='1', help='arg help [%(default)s]')


@argcmd.command(some_crazy_name)
def foo(args):
    """Registered via decorator"""
    print args.arg


def args_bar(parser):
    parser.add_argument('arg', help='arg help')


def cmd_bar(args):
    """Registered via name"""
    print args.arg


if __name__ == '__main__':
    argcmd.main()
