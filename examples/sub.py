#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argcmd


def opts_foo(parser):
    parser.add_argument('-b', '--bar')


def cmd_foo(args):
    """Example foo"""
    print args.bar


if __name__ == '__main__':
    # TODO hide globals
    argcmd.main(globals())
