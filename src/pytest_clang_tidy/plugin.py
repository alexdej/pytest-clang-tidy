import subprocess
import sysconfig
import warnings

import pytest
from clang_tidy import _get_executable

CLANG_TIDY_BIN = str(_get_executable("clang-tidy"))
CACHE_KEY = "clang-tidy/mtimes"


def pytest_addoption(parser):
    group = parser.getgroup("clang-tidy", "clang-tidy static analysis")
    group.addoption(
        "--clang-tidy",
        action="store_true",
        default=False,
        help="run clang-tidy on C/C++ source files",
    )
    parser.addini(
        "clang_tidy_extensions",
        type="args",
        default=[".c", ".cpp", ".cc", ".cxx"],
        help="file extensions to collect for clang-tidy (default: .c .cpp .cc .cxx)",
    )
    parser.addini(
        "clang_tidy_checks",
        type="args",
        default=[],
        help="checks to enable (joined with commas and passed as -checks=...)",
    )
    parser.addini(
        "clang_tidy_args",
        type="args",
        default=[],
        help="extra arguments forwarded to every clang-tidy invocation",
    )
    parser.addini(
        "clang_tidy_compiler_args",
        type="args",
        default=[],
        help="extra compiler arguments passed after -- (e.g. -std=c11 -DFOO)",
    )
    parser.addini(
        "clang_tidy_include_python_headers",
        type="bool",
        default=False,
        help="add -isystem<python_include> to compiler flags (for C extension projects)",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "clang_tidy: clang-tidy static analysis test")
    if not config.getoption("clang_tidy"):
        return
    cache = getattr(config, "cache", None)
    config._clang_tidy_mtimes = cache.get(CACHE_KEY, {}) if cache else {}


def pytest_unconfigure(config):
    mtimes = getattr(config, "_clang_tidy_mtimes", None)
    if mtimes is None:
        return
    cache = getattr(config, "cache", None)
    if cache:
        cache.set(CACHE_KEY, mtimes)


def pytest_collect_file(parent, file_path):
    if not parent.config.getoption("clang_tidy"):
        return None
    extensions = parent.config.getini("clang_tidy_extensions")
    if file_path.suffix in extensions:
        return ClangTidyFile.from_parent(parent, path=file_path)
    return None


def _has_compile_commands(config):
    return (config.rootpath / "compile_commands.json").is_file()


class ClangTidyError(Exception):
    pass


class ClangTidyWarning(UserWarning):
    pass


class ClangTidyFile(pytest.File):
    def collect(self):
        item = ClangTidyItem.from_parent(self, name="CLANG_TIDY")
        item.add_marker(pytest.mark.clang_tidy)
        yield item


class ClangTidyItem(pytest.Item):
    def setup(self):
        mtimes = getattr(self.config, "_clang_tidy_mtimes", {})
        self._mtime = self.path.stat().st_mtime_ns
        checks = self.config.getini("clang_tidy_checks")
        args = self.config.getini("clang_tidy_args")
        compiler_args = self.config.getini("clang_tidy_compiler_args")
        old = mtimes.get(str(self.path))
        if old == [self._mtime, checks, args, compiler_args]:
            pytest.skip("previously passed clang-tidy")

    def runtest(self):
        checks = self.config.getini("clang_tidy_checks")
        args = self.config.getini("clang_tidy_args")
        compiler_args = self.config.getini("clang_tidy_compiler_args")
        cmd = [CLANG_TIDY_BIN, "--quiet", "--allow-no-checks"]
        if checks:
            cmd.append(f"-checks={','.join(checks)}")
        cmd += args + [str(self.path)]
        if not _has_compile_commands(self.config):
            extra = []
            if self.config.getini("clang_tidy_include_python_headers"):
                python_include = sysconfig.get_path("include")
                extra.append(f"-isystem{python_include}")
            if extra or compiler_args:
                cmd += ["--"] + extra + compiler_args
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            output = result.stdout or result.stderr
            if not output:
                output = f"clang-tidy exited with code {result.returncode}"
            raise ClangTidyError(output)
        # Emit warnings for passing files that still had output
        if result.stdout.strip():
            warnings.warn(
                f"\n{result.stdout.strip()}",
                ClangTidyWarning,
                stacklevel=1,
            )
        # Cache only on success
        if hasattr(self.config, "_clang_tidy_mtimes"):
            self._mtime = getattr(self, "_mtime", self.path.stat().st_mtime_ns)
            self.config._clang_tidy_mtimes[str(self.path)] = [
                self._mtime,
                checks,
                args,
                compiler_args,
            ]

    def repr_failure(self, excinfo):
        if excinfo.errisinstance(ClangTidyError):
            return str(excinfo.value)
        return super().repr_failure(excinfo)

    def reportinfo(self):
        return self.path, None, f"{self.path}::CLANG_TIDY"
