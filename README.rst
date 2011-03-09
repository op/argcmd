argcmd
======

Easy sub-command program creation with argument parsing and interactive shell.

Together with the power of `argparse`_, this small library removes most of the
boiler plate you often write when you need to create python programs. It
gathers all commands from one module and presents them as sub-commands, similar
to eg. git.

It also comes with an optional interactive shell. When your program is run
without any specific sub-command, a readline based shell is started which
has simple command completion and history (currently via ``--enable-history``).
Think of eg. gdb.

.. _argparse: http://code.google.com/p/argparse/

Usage
-----

There are two ways of creating programs. First way is by prefixing the method
names with ``cmd_`` or registering them with the ``@command``-decorator.

Second way is by subclassing the ``ArgCommand`` class. The advantage with this
way is that you will have a unified way to setup and teardown your class
through callbacks.

Arguments can be added both using a function, either prefixed ``args_`` or
added as argument to the ``@command``-decorator, -- or you can use the
``@argument``-decorator. A small sample::

    import argcmd

    class Example(argcmd.ArgCmd):
        def init(self):
            self.calls = 0

        def exit(self):
            print 'called:', self.calls

        @argcmd.argument('arg', help='arg help')
        def bar(self, args):
            self.calls += 1
            print 'arg:', args.arg

    if __name__ == '__main__':
        argcmd.main()

If this command is run via the interactive shell, the counter will increase
for each call.

See examples for more information. For information about the parser, please
see argparse.

Related
-------

If this library is not for you, don't worry. Many great projects by great
people exists with similar goals as this one.

* https://github.com/anandology/subcommand/
* https://github.com/simonw/optfunc
* http://code.google.com/p/cmdln/
