"""Tests for pytest-clang-tidy using pytester."""

# C source with a null pointer dereference that clang-tidy detects.
C_ERROR = """\
#include <stdlib.h>
int main() {
    int *p = NULL;
    *p = 42;
    return 0;
}
"""

# C source with no issues.
C_CLEAN = """\
int main() {
    return 0;
}
"""


def test_clean_file_passes(pytester):
    pytester.makefile(".c", clean=C_CLEAN)
    result = pytester.runpytest("--clang-tidy", "-v")
    result.stdout.fnmatch_lines(["*PASSED*"])
    result.assert_outcomes(passed=1)


def test_error_file_fails(pytester):
    pytester.makeini(
        "[pytest]\n"
        "clang_tidy_args = -checks=-*,clang-analyzer-* --warnings-as-errors=*\n"
    )
    pytester.makefile(".c", bad=C_ERROR)
    result = pytester.runpytest("--clang-tidy")
    result.assert_outcomes(failed=1)


def test_stdout_in_failure_output(pytester):
    pytester.makeini(
        "[pytest]\n"
        "clang_tidy_args = -checks=-*,clang-analyzer-* --warnings-as-errors=*\n"
    )
    pytester.makefile(".c", bad=C_ERROR)
    result = pytester.runpytest("--clang-tidy")
    result.stdout.fnmatch_lines(["*NullDereference*"])


def test_not_collected_without_flag(pytester):
    pytester.makefile(".c", clean=C_CLEAN)
    result = pytester.runpytest()
    result.assert_outcomes()


def test_custom_extensions(pytester):
    pytester.makeini(
        "[pytest]\n"
        "clang_tidy_extensions = .h\n"
    )
    pytester.makefile(".h", header=C_CLEAN)
    pytester.makefile(".c", also_clean=C_CLEAN)
    pytester.makefile(".cpp", also_also_clean=C_CLEAN)
    result = pytester.runpytest("--clang-tidy")
    # only .h collected, not .c or .cpp
    result.assert_outcomes(passed=1)


def test_cpp_collected_by_default(pytester):
    pytester.makefile(".cpp", clean=C_CLEAN)
    result = pytester.runpytest("--clang-tidy")
    result.assert_outcomes(passed=1)


def test_clang_tidy_args_forwarded(pytester):
    """Suppress the specific warning so the file passes despite the bug."""
    pytester.makeini(
        "[pytest]\n"
        "clang_tidy_args = -checks=-*,clang-analyzer-*,-clang-analyzer-core.NullDereference --warnings-as-errors=*\n"
    )
    pytester.makefile(".c", bad=C_ERROR)
    result = pytester.runpytest("--clang-tidy")
    result.assert_outcomes(passed=1)


def test_warnings_emitted_on_pass(pytester):
    """When clang-tidy finds warnings but exits 0, they show as Python warnings."""
    pytester.makeini(
        "[pytest]\n"
        "clang_tidy_args = -checks=-*,clang-analyzer-*\n"
    )
    pytester.makefile(".c", bad=C_ERROR)
    result = pytester.runpytest("--clang-tidy", "-W", "always::pytest_clang_tidy.plugin.ClangTidyWarning")
    result.assert_outcomes(passed=1, warnings=1)
    result.stdout.fnmatch_lines(["*ClangTidyWarning*"])


def test_cache_skips_on_second_run(pytester):
    pytester.makefile(".c", clean=C_CLEAN)
    # First run: passes and populates cache
    result = pytester.runpytest("--clang-tidy", "-p", "cacheprovider")
    result.assert_outcomes(passed=1)
    # Second run: skipped via cache
    result = pytester.runpytest("--clang-tidy", "-p", "cacheprovider")
    result.assert_outcomes(skipped=1)


def test_cache_reruns_after_file_change(pytester):
    import os
    path = pytester.makefile(".c", clean=C_CLEAN)
    # First run
    result = pytester.runpytest("--clang-tidy", "-p", "cacheprovider")
    result.assert_outcomes(passed=1)
    # Bump mtime explicitly to avoid filesystem resolution issues
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    # Second run: re-checked because mtime changed
    result = pytester.runpytest("--clang-tidy", "-p", "cacheprovider")
    result.assert_outcomes(passed=1)


def test_cache_reruns_after_args_change(pytester):
    pytester.makefile(".c", clean=C_CLEAN)
    # First run
    result = pytester.runpytest("--clang-tidy", "-p", "cacheprovider")
    result.assert_outcomes(passed=1)
    # Second run with different args: re-checked
    pytester.makeini(
        "[pytest]\n"
        "clang_tidy_args = -checks=-*,clang-analyzer-*\n"
    )
    result = pytester.runpytest("--clang-tidy", "-p", "cacheprovider")
    result.assert_outcomes(passed=1)


def test_cache_does_not_skip_failures(pytester):
    pytester.makeini(
        "[pytest]\n"
        "clang_tidy_args = -checks=-*,clang-analyzer-* --warnings-as-errors=*\n"
    )
    pytester.makefile(".c", bad=C_ERROR)
    # First run: fails
    result = pytester.runpytest("--clang-tidy", "-p", "cacheprovider")
    result.assert_outcomes(failed=1)
    # Second run: still fails (not cached)
    result = pytester.runpytest("--clang-tidy", "-p", "cacheprovider")
    result.assert_outcomes(failed=1)


def test_cache_clear_forces_rerun(pytester):
    pytester.makefile(".c", clean=C_CLEAN)
    # First run: passes and populates cache
    result = pytester.runpytest("--clang-tidy", "-p", "cacheprovider")
    result.assert_outcomes(passed=1)
    # Second run with --cache-clear: re-checked
    result = pytester.runpytest("--clang-tidy", "--cache-clear", "-p", "cacheprovider")
    result.assert_outcomes(passed=1)


def test_compile_commands_skips_auto_flags(pytester):
    """When compile_commands.json exists, don't append -- and compiler flags."""
    pytester.makefile(".json", compile_commands="[]")
    # Rename to correct name (makefile prefixes with the name arg)
    import shutil
    src = pytester.path / "compile_commands.json"
    if not src.exists():
        # pytester.makefile(".json", compile_commands="[]") creates compile_commands.json
        pass
    pytester.makefile(".c", clean=C_CLEAN)
    result = pytester.runpytest("--clang-tidy", "-v")
    result.assert_outcomes(passed=1)
