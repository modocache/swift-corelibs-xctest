#!/usr/bin/env python
# build_script.py - Build, install, and test XCTest -*- python -*-
#
# This source file is part of the Swift.org open source project
#
# Copyright (c) 2014 - 2016 Apple Inc. and the Swift project authors
# Licensed under Apache License v2.0 with Runtime Library Exception
#
# See http://swift.org/LICENSE.txt for license information
# See http://swift.org/CONTRIBUTORS.txt for the list of Swift project authors

import argparse
import glob
import os
import subprocess
import sys
import tempfile
import textwrap
import platform

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))


def main(args=sys.argv[1:]):
    """
    The main entry point for this script. Based on the subcommand given,
    delegates building or testing XCTest to a sub-parser and its corresponding
    function.
    """
    strategy = DarwinStrategy if platform.system() == 'Darwin' else GenericUnixStrategy

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent("""
            Build, test, and install XCTest.

            NOTE: In general this script should not be invoked directly. The
            recommended way to build and test XCTest is via the Swift build
            script. See this project's README for details.

            The Swift build script invokes this %(prog)s script to build,
            test, and install this project. You may invoke it in the same way
            to build this project directly. For example, if you are in a Linux
            environment, your install of Swift is located at "/swift" and you
            wish to install XCTest into that same location, here is a sample
            invocation of the build script:

            $ %(prog)s \\
                --swiftc="/swift/usr/bin/swiftc" \\
                --build-dir="/tmp/XCTest_build" \\
                --foundation-build-dir "/swift/usr/lib/swift/linux" \\
                --library-install-path="/swift/usr/lib/swift/linux" \\
                --module-install-path="/swift/usr/lib/swift/linux/x86_64"

            Note that installation is not supported on Darwin as this library
            is only intended to be used as a dependency in environments where
            Apple XCTest is not available.
            """))
    subparsers = parser.add_subparsers(
        description=textwrap.dedent("""
            Use one of these to specify whether to build, test, or install
            XCTest. If you don't specify any of these, 'build' is executed as a
            default. You may also use 'build' to also test and install the
            built products. Pass the -h or --help option to any of the
            subcommands for more information."""))

    build_parser = subparsers.add_parser(
        "build",
        description=textwrap.dedent("""
            Build XCTest.so, XCTest.swiftmodule, and XCTest.swiftdoc using the
            given Swift compiler. This command may also test and install the
            built products."""))
    build_parser.set_defaults(func=strategy.build)
    build_parser.add_argument(
        "--swiftc",
        help="Path to the 'swiftc' compiler that will be used to build "
             "XCTest.so, XCTest.swiftmodule, and XCTest.swiftdoc. This will "
             "also be used to build the tests for those built products if the "
             "--test option is specified.",
        required=True)
    build_parser.add_argument(
        "--build-dir",
        help="Path to the output build directory. If not specified, a "
             "temporary directory is used.",
        default=tempfile.mkdtemp())
    build_parser.add_argument(
        "--foundation-build-dir",
        help="Path to swift-corelibs-foundation build products, which "
             "the built XCTest.so will be linked against.",
        required=strategy.requires_foundation_build_dir())
    build_parser.add_argument(
        "--foundation-install-prefix",
        help="Path to the installation location for swift-corelibs-foundation "
             "build products ('%(default)s' by default); CoreFoundation "
             "dependencies are expected to be found under "
             "FOUNDATION_BUILD_DIR/FOUNDATION_INSTALL_PREFIX.",
        default="/usr")
    build_parser.add_argument(
        "--libdispatch-build-dir",
        help="Path to swift-corelibs-libdispatch build products, which "
             "the built XCTest.so will be linked against.")
    build_parser.add_argument(
        "--libdispatch-src-dir",
        help="Path to swift-corelibs-libdispatch source tree, which "
             "the built XCTest.so will be linked against.")
    build_parser.add_argument(
        "--module-install-path",
        help="Location at which to install XCTest.swiftmodule and "
             "XCTest.swiftdoc. This directory will be created if it doesn't "
             "already exist.",
        dest="module_path")
    build_parser.add_argument(
        "--library-install-path",
        help="Location at which to install XCTest.so. This directory will be "
             "created if it doesn't already exist.",
        dest="lib_path")
    build_parser.add_argument(
        "--release",
        help="builds for release",
        action="store_const",
        dest="build_style",
        const="release",
        default="debug")
    build_parser.add_argument(
        "--debug",
        help="builds for debug (the default)",
        action="store_const",
        dest="build_style",
        const="debug",
        default="debug")
    build_parser.add_argument(
        "--test",
        help="Whether to run tests after building. Note that you must have "
             "cloned https://github.com/apple/swift-llvm at {} in order to "
             "run this command.".format(os.path.join(
                 os.path.dirname(SOURCE_DIR), 'llvm')),
        action="store_true")

    test_parser = subparsers.add_parser(
        "test",
        description="Tests a built XCTest framework at the given path.")
    test_parser.set_defaults(func=strategy.test)
    test_parser.add_argument(
        "build_dir",
        help="An absolute path to a directory containing the built XCTest.so "
             "library.")
    test_parser.add_argument(
        "--swiftc",
        help="Path to the 'swiftc' compiler used to build and run the tests.",
        required=True)
    test_parser.add_argument(
        "--lit",
        help="Path to the 'lit' tester tool used to run the test suite. "
             "'%(default)s' by default.",
        default=os.path.join(os.path.dirname(SOURCE_DIR),
                             "llvm", "utils", "lit", "lit.py"))
    test_parser.add_argument(
        "--foundation-build-dir",
        help="Path to swift-corelibs-foundation build products, which the "
             "tests will be linked against.",
        required=strategy.requires_foundation_build_dir())
    test_parser.add_argument(
        "--foundation-install-prefix",
        help="Path to the installation location for swift-corelibs-foundation "
             "build products ('%(default)s' by default); CoreFoundation "
             "dependencies are expected to be found under "
             "FOUNDATION_BUILD_DIR/FOUNDATION_INSTALL_PREFIX.",
        default="/usr")
    test_parser.add_argument(
        "--libdispatch-build-dir",
        help="Path to swift-corelibs-libdispatch build products, which "
             "the built XCTest.so will be linked against.")
    test_parser.add_argument(
        "--libdispatch-src-dir",
        help="Path to swift-corelibs-libdispatch source tree, which "
             "the built XCTest.so will be linked against.")

    install_parser = subparsers.add_parser(
        "install",
        description="Installs a built XCTest framework.")
    install_parser.set_defaults(func=strategy.install)
    install_parser.add_argument(
        "build_dir",
        help="An absolute path to a directory containing a built XCTest.so, "
             "XCTest.swiftmodule, and XCTest.swiftdoc.")
    install_parser.add_argument(
        "-m", "--module-install-path",
        help="Location at which to install XCTest.swiftmodule and "
             "XCTest.swiftdoc. This directory will be created if it doesn't "
             "already exist.")
    install_parser.add_argument(
        "-l", "--library-install-path",
        help="Location at which to install XCTest.so. This directory will be "
             "created if it doesn't already exist.")

    # Many versions of Python require a subcommand must be specified.
    # We handle this here: if no known subcommand (or none of the help options)
    # is included in the arguments, then insert the default subcommand
    # argument: 'build'.
    if any([a in ["build", "test", "install", "-h", "--help"] for a in args]):
        parsed_args = parser.parse_args(args=args)
    else:
        parsed_args = parser.parse_args(args=["build"] + args)

    # Execute the function for the subcommand we've been given.
    parsed_args.func(parsed_args)


if __name__ == '__main__':
    main()
