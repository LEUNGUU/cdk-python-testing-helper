import os
import json
import logging
import inspect
import subprocess
import pickle

from typing import Dict, List
from pathlib import Path
from hashlib import sha1
from collections import namedtuple


_LOGGER = logging.getLogger("cdktest")

CDKCommandOutput = namedtuple("CDKCommandOutput", "retcode out err")


class CDKTestError(Exception):
    pass


def parse_args():
    pass


class CDKTest:
    """Helper class for use in testing CDK stacks.

    This helper class can be used to set up fixtures in CDK tests.

    """

    def __init__(
        self,
        appdir: str,
        basedir: str = None,
        binary: str = "cdk",
        env: Dict[str, str] = None,
        enable_cache: bool = False,
        cache_dir: str = None,
    ):
        """Set cdk app folder to operate on and optional base directory."""
        self._basedir = basedir or os.getcwd()
        self.binary = binary
        self.appdir = (
            appdir if Path(appdir).is_absolute() else Path(self._basedir) / appdir
        )
        self.env = os.environ.copy()
        self.enable_cache = enable_cache
        if not cache_dir:
            self.cache_dir = (
                Path(os.path.dirname(inspect.stack()[1].filename)) / ".cdktest-cache"
            )
        else:
            self.cache_dir = Path(cache_dir)
        if env:
            self.env.update(env)

    def _dirhash(
        self,
        directory: str,
        hash,
        ignore_hidden: bool = True,
        exclude_directories: List[str] = [],
        excluded_extensions: List[str] = [],
    ):
        """Returns hash of directory's file contents"""
        assert Path(directory).is_dir()
        try:
            dir_iter = sorted(Path(directory).iterdir(), key=lambda p: str(p).lower())
        except FileNotFoundError:
            return hash
        for path in dir_iter:
            if path.is_file():
                if ignore_hidden and path.name.startswith("."):
                    continue
                if path.suffix in excluded_extensions:
                    continue
                with open(path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash.update(chunk)
            if path.is_dir() and path.name not in exclude_directories:
                hash = self._dirhash(
                    path,
                    hash,
                    ignore_hidden=ignore_hidden,
                    exclude_directories=exclude_directories,
                    excluded_extensions=excluded_extensions,
                )
        return hash

    def generate_cache_hash(self) -> str:
        """Returns a hash value using the instance attributes"""
        params = {
            **{
                k: v
                for k, v in self.__dict__.items()
                if k in ["binary", "_basedir", "appdir", "_env"]
            }
        }
        params["appdir"] = self._dirhash(
            self.appdir, sha1(), ignore_hidden=True, exclude_directories=["cdk.out"]
        )
        return (
            sha1(
                json.dumps(params, sort_keys=True, default=str).encode("cp037")
            ).hexdigest()
            + ".pickle"
        )

    def _cache(func):
        def cache(self, **kwargs):
            """
            Runs the cdktest instance method or retreives the cache value if it exists

            Args:
                kwargs: Keyword arguments that are passed to the decorated method
            Returns:
                Output of the cdktest instance method
            """
            _LOGGER.info(f"Cache decorated method: {func.__name__}")

            if not self.enable_cache or not kwargs.get("use_cache", False):
                return func(self, **kwargs)

            cache_dir = (
                self.cache_dir
                / Path(sha1(self.appdir.encode("cp037")).hexdigest())
                / Path(func.__name__)
            )
            cache_dir.mkdir(parents=True, exist_ok=True)
            hash_filename = self.generate_cache_hash()
            cache_key = cache_dir / hash_filename
            _LOGGER.debug("Cache key: %s", cache_key)

            try:
                f = cache_key.open("rb")
            except OSError:
                _LOGGER.debug("Could not read from cache path")
            else:
                _LOGGER.info("Getting output from cache")
                return pickle.load(f)

            _LOGGER.info("Running Command")
            out = func(self, **kwargs)

            if out:
                hash_filename = self.generate_cache_hash()
                cache_key = cache_dir / hash_filename
                _LOGGER.debug("Cache key: %s", cache_key)

                _LOGGER.info("Writing command to cache")
                try:
                    f = cache_key.open("wb")
                except OSError as e:
                    _LOGGER.error("Cache could not be written to path")
                else:
                    with f:
                        pickle.dump(out, f, pickle.HIGHEST_PROTOCOL)
            return out

        return cache

    def setup(self) -> str:
        """Run cdk bootstrap command."""
        return self.execute_command("bootstrap").out

    def synthesize(self) -> str:
        """Run cdk synthesize command."""
        # check if cdk.json exists
        dir_iter = sorted(Path(self.appdir).iterdir(), key=lambda p: str(p).lower())
        cmd_args = ["-a", '"python3 app.py"']
        for path in dir_iter:
            if path.is_file() and path.name == "cdk.json":
                cmd_args = []
                break
        return self.execute_command("synthesize", *cmd_args).out

    def deploy(self) -> str:
        """Run cdk deploy command."""
        return self.execute_command("deploy").out

    def destroy(self) -> str:
        """Run cdk destroy command."""
        return self.execute_command("destroy").out

    def execute_command(self, cmd: str, *cmd_args) -> None:
        """Run arbitrary CDK command."""
        _LOGGER.debug([cmd, cmd_args])
        cmdline = [self.binary, cmd]
        cmdline.extend(cmd_args)
        _LOGGER.info(" ".join(cmdline))
        _LOGGER.info(self.appdir)
        retcode, full_output_lines = None, []
        try:
            stderr_mode = subprocess.STDOUT if os.name == "nt" else subprocess.PIPE
            p = subprocess.Popen(
                cmdline,
                stdout=subprocess.PIPE,
                stderr=stderr_mode,
                shell=True,  # need this in nixshell
                cwd=self.appdir,
                env=self.env,
                universal_newlines=True,
                encoding="utf-8",
                errors="ignore",
            )
            while True:
                output = p.stdout.readline()
                if output == "" and p.poll() is not None:
                    break
                if output:
                    _LOGGER.info(output.strip())
                    full_output_lines.append(output)
            retcode = p.poll()
            p.wait()
        except FileNotFoundError as e:
            raise CDKTestError(f"CDK executable not found: {e}")
        out, err = p.communicate()
        full_output = "".join(full_output_lines)
        if retcode in [1, 11]:
            message = f"Error running command {cmd}: {retcode} {full_output} {err}"
            _LOGGER.critical(message)
            raise CDKTestError(message, err)
        print(full_output)
        return CDKCommandOutput(retcode, full_output, err)
