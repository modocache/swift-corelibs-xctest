from __future__ import print_function

import errno
import os
import subprocess


def note(msg):
    """Print a message, prefixed with 'xctest-build'."""
    print("xctest-build: " + msg)


def run(command):
    """Print the command to be executed, then execute it."""
    note(command)
    subprocess.check_call(command, shell=True)


def mkdirp(path):
    """
    Create a directory at the given path if it doesn't already exist.
    """
    if not os.path.exists(path):
        run("mkdir -p {}".format(path))


def symlink_force(target, link_name):
    """
    Create a symlink to the target at the path link_name.
    If a file already exists at link_name, overwrite it.
    """
    if os.path.isdir(link_name):
        link_name = os.path.join(link_name, os.path.basename(target))
    try:
        os.symlink(target, link_name)
    except OSError as e:
        if e.errno == errno.EEXIST:
            os.remove(link_name)
            os.symlink(target, link_name)
        else:
            raise e
