import io

import unidiff


def parse_diff(diff: str) -> unidiff.PatchSet:
    """parse file diff content to unidiff.PatchSet

    diff content has a format of:
    --- a/aaa.txt
    +++ b/bbb.txt
    (diff contents)
    """
    return unidiff.PatchSet(io.StringIO(diff))[0]


def parse_patch_file(patch: str, prev_name: str, name: str):
    """parse file patch content to unidiff.PatchSet"""
    return unidiff.PatchSet(io.StringIO(f"""--- a/{prev_name}\n+++ b/{name}\n{patch}"""))[0]
