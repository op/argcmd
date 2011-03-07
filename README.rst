argcmd
======

Easy sub-command program creation with argument parsing and interactive shell.

Together with the power of argparse, this small library removes most of the
boiler plate you often write when you need to create python programs. It
gathers all commands from one module and presents them as sub-commands, similar
to eg. git.

As a small bonus, it also comes with an interactive shell. When your program is
run without any specific sub-command, a readline based shell is started which
has simple command completion and history (currently via --enable-history).

Usage
-----

There are two ways of creating programs. First way is just to create simple
methods, either prefixed with cmd_ or registered with the command-decorator.

Second way is by subclassing the ArgCommand class. The advantage with this
way is that you will have a unified way to setup and teardown your class
through callbacks. Example:

class Example(argcmd.ArgCommand):
    def init(self):
        self.calls = 0

    def args_bar(self, parser):
        parser.add_argument('arg', help='arg help')

    def cmd_bar(self, args):
        self.calls += 1
        print 'bar', self.calls, 'arg', args.arg

If this command is run via the interactive shell, the counter will increase
for each call.

See examples for more information. For information about the parser, please
see argparse.
