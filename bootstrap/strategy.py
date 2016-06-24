import os

from bootstrap.main import main
from bootstrap.os import note, run

class DarwinStrategy:
    @staticmethod
    def requires_foundation_build_dir():
        # The Foundation build directory is not required on Darwin because the
        # Xcode workspace implicitly builds Foundation when building the XCTest
        # schemes.
        return False

    @staticmethod
    def build(args):
        """
        Build XCTest and place the built products in the given 'build_dir'.
        If 'test' is specified, also executes the 'test' subcommand.
        """
        swiftc = os.path.abspath(args.swiftc)
        build_dir = os.path.abspath(args.build_dir)

        run("xcodebuild -workspace {source_dir}/XCTest.xcworkspace "
            "-scheme SwiftXCTest "
            "SWIFT_EXEC=\"{swiftc}\" "
            "SWIFT_LINK_OBJC_RUNTIME=YES "
            "SYMROOT=\"{build_dir}\" OBJROOT=\"{build_dir}\"".format(
                swiftc=swiftc,
                build_dir=build_dir,
                source_dir=SOURCE_DIR))

        if args.test:
            # Execute main() using the arguments necessary to run the tests.
            main(args=["test",
                       "--swiftc", swiftc,
                       build_dir])

    @staticmethod
    def test(args):
        """
        Test SwiftXCTest.framework, using the given 'swiftc' compiler, looking
        for it in the given 'build_dir'.
        """
        swiftc = os.path.abspath(args.swiftc)
        build_dir = os.path.abspath(args.build_dir)

        run("xcodebuild -workspace {source_dir}/XCTest.xcworkspace "
            "-scheme SwiftXCTestFunctionalTests "
            "SWIFT_EXEC=\"{swiftc}\" "
            "SWIFT_LINK_OBJC_RUNTIME=YES "
            "SYMROOT=\"{build_dir}\" OBJROOT=\"{build_dir}\" "
            "| grep -v \"    export\"".format(
                swiftc=swiftc,
                build_dir=build_dir,
                source_dir=SOURCE_DIR))

    @staticmethod
    def install(args):
        """
        Installing XCTest is not supported on Darwin.
        """
        _note("error: The install command is not supported on this platform")
        exit(1)


class GenericUnixStrategy:
    @staticmethod
    def requires_foundation_build_dir():
        # This script does not know how to build Foundation in Unix environments,
        # so we need the path to a pre-built Foundation library.
        return True

    @staticmethod
    def build(args):
        """
        Build XCTest and place the built products in the given 'build_dir'.
        If 'test' is specified, also executes the 'test' subcommand.
        """
        swiftc = os.path.abspath(args.swiftc)
        build_dir = os.path.abspath(args.build_dir)
        foundation_build_dir = os.path.abspath(args.foundation_build_dir)
        core_foundation_build_dir = GenericUnixStrategy.core_foundation_build_dir(
            foundation_build_dir, args.foundation_install_prefix)
        if args.libdispatch_build_dir:
            libdispatch_build_dir = os.path.abspath(args.libdispatch_build_dir)
        if args.libdispatch_src_dir:
            libdispatch_src_dir = os.path.abspath(args.libdispatch_src_dir)

        _mkdirp(build_dir)

        sourcePaths = glob.glob(os.path.join(
            SOURCE_DIR, 'Sources', 'XCTest', '*', '*.swift'))

        if args.build_style == "debug":
            style_options = "-g"
        else:
            style_options = "-O"

        # Not incremental..
        # Build library
        if args.libdispatch_build_dir and args.libdispatch_src_dir:
            libdispatch_args = "-I {libdispatch_build_dir}/src -I {libdispatch_src_dir} ".format(
                libdispatch_build_dir=libdispatch_build_dir,
                libdispatch_src_dir=libdispatch_src_dir)
        else:
            libdispatch_args = ""

        run("{swiftc} -Xcc -fblocks -c {style_options} -emit-object -emit-module "
            "-module-name XCTest -module-link-name XCTest -parse-as-library "
            "-emit-module-path {build_dir}/XCTest.swiftmodule "
            "-force-single-frontend-invocation "
            "-I {foundation_build_dir} -I {core_foundation_build_dir} "
            "{libdispatch_args} "
            "{source_paths} -o {build_dir}/XCTest.o".format(
                swiftc=swiftc,
                style_options=style_options,
                build_dir=build_dir,
                foundation_build_dir=foundation_build_dir,
                core_foundation_build_dir=core_foundation_build_dir,
                libdispatch_args=libdispatch_args,
                source_paths=" ".join(sourcePaths)))
        run("{swiftc} -emit-library {build_dir}/XCTest.o "
            "-L {foundation_build_dir} -lswiftGlibc -lswiftCore -lFoundation -lm "
            # We embed an rpath of `$ORIGIN` to ensure other referenced
            # libraries (like `Foundation`) can be found solely via XCTest.
            "-Xlinker -rpath=\\$ORIGIN "
            "-o {build_dir}/libXCTest.so".format(
                swiftc=swiftc,
                build_dir=build_dir,
                foundation_build_dir=foundation_build_dir))

        if args.test:
            # Execute main() using the arguments necessary to run the tests.
            main(args=["test",
                       "--swiftc", swiftc,
                       "--foundation-build-dir", foundation_build_dir,
                       build_dir])

        # If --module-install-path and --library-install-path were specified,
        # we also install the built XCTest products.
        if args.module_path is not None and args.lib_path is not None:
            # Execute main() using the arguments necessary for installation.
            main(args=["install", build_dir,
                       "--module-install-path", args.module_path,
                       "--library-install-path", args.lib_path])

        _note('Done.')

    @staticmethod
    def test(args):
        """
        Test the built XCTest.so library at the given 'build_dir', using the
        given 'swiftc' compiler.
        """
        lit_path = os.path.abspath(args.lit)
        if not os.path.exists(lit_path):
            raise IOError(
                'Could not find lit tester tool at path: "{}". This tool is '
                'requred to run the test suite. Unless you specified a custom '
                'path to the tool using the "--lit" option, the lit tool will be '
                'found in the LLVM source tree, which is expected to be checked '
                'out in the same directory as swift-corelibs-xctest. If you do '
                'not have LLVM checked out at this path, you may follow the '
                'instructions for "Getting Sources for Swift and Related '
                'Projects" from the Swift project README in order to fix this '
                'error.'.format(lit_path))

        # FIXME: Allow these to be specified by the Swift build script.
        lit_flags = "-sv --no-progress-bar"
        tests_path = os.path.join(SOURCE_DIR, "Tests", "Functional")
        foundation_build_dir = os.path.abspath(args.foundation_build_dir)
        core_foundation_build_dir = GenericUnixStrategy.core_foundation_build_dir(
            foundation_build_dir, args.foundation_install_prefix)
        if args.libdispatch_build_dir:
            libdispatch_build_dir = os.path.abspath(args.libdispatch_build_dir)
            symlink_force(os.path.join(args.libdispatch_build_dir, "src", ".libs", "libdispatch.so"),
                foundation_build_dir)
        if args.libdispatch_src_dir and args.libdispatch_build_dir:
            libdispatch_src_args = "LIBDISPATCH_SRC_DIR={libdispatch_src_dir} LIBDISPATCH_BUILD_DIR={libdispatch_build_dir}".format(
                libdispatch_src_dir=os.path.abspath(args.libdispatch_src_dir),
                libdispatch_build_dir=os.path.join(args.libdispatch_build_dir, 'src', '.libs'))
        else:
            libdispatch_src_args = ""

        run('SWIFT_EXEC={swiftc} '
            'BUILT_PRODUCTS_DIR={built_products_dir} '
            'FOUNDATION_BUILT_PRODUCTS_DIR={foundation_build_dir} '
            'CORE_FOUNDATION_BUILT_PRODUCTS_DIR={core_foundation_build_dir} '
            '{libdispatch_src_args} '
            '{lit_path} {lit_flags} '
            '{tests_path}'.format(
                swiftc=os.path.abspath(args.swiftc),
                built_products_dir=args.build_dir,
                foundation_build_dir=foundation_build_dir,
                core_foundation_build_dir=core_foundation_build_dir,
                libdispatch_src_args=libdispatch_src_args,
                lit_path=lit_path,
                lit_flags=lit_flags,
                tests_path=tests_path))

    @staticmethod
    def install(args):
        """
        Install the XCTest.so, XCTest.swiftmodule, and XCTest.swiftdoc build
        products into the given module and library paths.
        """
        build_dir = os.path.abspath(args.build_dir)
        module_install_path = os.path.abspath(args.module_install_path)
        library_install_path = os.path.abspath(args.library_install_path)

        _mkdirp(module_install_path)
        _mkdirp(library_install_path)

        xctest_so = "libXCTest.so"
        run("cp {} {}".format(
            os.path.join(build_dir, xctest_so),
            os.path.join(library_install_path, xctest_so)))

        xctest_swiftmodule = "XCTest.swiftmodule"
        run("cp {} {}".format(
            os.path.join(build_dir, xctest_swiftmodule),
            os.path.join(module_install_path, xctest_swiftmodule)))

        xctest_swiftdoc = "XCTest.swiftdoc"
        run("cp {} {}".format(
            os.path.join(build_dir, xctest_swiftdoc),
            os.path.join(module_install_path, xctest_swiftdoc)))

    @staticmethod
    def core_foundation_build_dir(foundation_build_dir, foundation_install_prefix):
        """
        Given the path to a swift-corelibs-foundation built product directory,
        return the path to CoreFoundation built products.

        When specifying a built Foundation dir such as
        '/build/foundation-linux-x86_64/Foundation', CoreFoundation dependencies
        are placed in 'usr/lib/swift'. Note that it's technically not necessary to
        include this extra path when linking the installed Swift's
        'usr/lib/swift/linux/libFoundation.so'.
        """
        return os.path.join(foundation_build_dir,
                            foundation_install_prefix.strip("/"), 'lib', 'swift')
