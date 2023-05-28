import os
import json
import logging
import inspect
import subprocess
import pickle
import weakref
import shutil

from typing import Dict, List, Any
from pathlib import Path
from hashlib import sha1
from collections import namedtuple, abc


__version__ = "0.0.1"

_LOGGER = logging.getLogger("cdktest")

CDKCommandOutput = namedtuple("CDKCommandOutput", "retcode out err")


class CDKTestError(Exception):
    "Customize Exception class"
    pass


def parse_args(cmd: str, appdir: str) -> List[str]:
    """Check cdk files and add arguments for use in CDK commands.

    Args:
      cmd: CDK subcommand name. It could be either synth, deploy or destroy
      appdir: The path to cdk folder.

    Returns:
      A list of command arguments for use with subprocess
    """
    cmd_args = ["--no-color", "--json"]
    file_list = [item.name for item in Path(appdir).glob("*")]
    if cmd != "synth":
        match cmd:
            case "deploy":
                cmd_args.extend(["--require-approval", "never"])
            case "destroy":
                cmd_args.append("--force")
            case _:
                raise CDKTestError('Only accept "deploy" and "destroy"')
    if "cdk.out" in file_list:
        cmd_args.extend(["-a", "cdk.out"])
    elif "cdk.json" in file_list:
        pass
    elif "app.py" in file_list:
        cmd_args.extend(["-a", '"python app.py"'])
    else:
        raise CDKTestError("Could not find app entry point")
    return cmd_args


class CFTemplateJSONBase(abc.Mapping):
    "Base class for JSON wrappers."

    def __init__(self, raw):
        self._raw = raw

    def __bytes__(self):
        return bytes(self._raw)

    def __getitem__(self, index):
        return self._raw[index]

    def __iter__(self):
        return iter(self._raw)

    def __len__(self):
        return len(self._raw)

    def __str__(self):
        return str(self._raw)


class CFTemplateResources(CFTemplateJSONBase):
    "Minimal wrapper for parsed cf template resources."

    def __init__(self, raw):
        super(CFTemplateResources, self).__init__(raw)
        self.all_resources = self._raw.get("Resources")
        self._resources = None

    @property
    def resources(self):
        if self._resources is None:
            resources = {item["Type"]: [] for item in self.all_resources.values()}
            for _, v in self.all_resources.items():
                resources[v["Type"]].append(v["Properties"])
            self._resources = resources
        return self._resources


class CDKTest:
    """Helper class for use in testing CDK stacks.

    This helper class can be used to set up fixtures in CDK tests, so that the
    usual CDK commands (synth, deploy, destroy) can be run on an cdk app.

    Args:
      appdir: The CDK app directory to test, either an absolute path, or relative to basedir.
      basedir: Optional base directory to use for relative paths, defaults to the
        directory above the one the cdk app lives in.
      binary: Path to cdk command.
      env: A dict wiith custom environment variables to pass to cdk.
      enable_cache: Determines if caching enabled for specific methods.
      cache_dir: Optional base directory to use for caching, defaults to
        the directory of the python file that instantiates this class
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
        # e.g. "npx cdk"
        self.binary = binary.split(" ")
        self.appdir = (
            appdir
            if Path(appdir).is_absolute()
            else os.path.join(self._basedir, appdir)
        )
        self.env = os.environ.copy()
        self.enable_cache = enable_cache
        self._template_formatter = lambda out: CFTemplateResources(json.loads(out))
        if not cache_dir:
            self.cache_dir = (
                Path(os.path.dirname(inspect.stack()[1].filename)) / ".cdktest-cache"
            )
        else:
            self.cache_dir = Path(cache_dir)
        if env:
            self.env.update(env)

        # cleanup when instance deletion
        self._finalizer = weakref.finalize(
            self, self._cleanup, self.appdir, self.cache_dir
        )

    @classmethod
    def _cleanup(
        cls,
        appdir: str,
        cache_dir: str,
        deep: bool = True,
        restore_files: bool = False,
    ) -> None:
        """Remove linked files, cdk.out and/or .cdktest-cache folder at instance deletion."""

        def remove_readonly(func, path, execinfo):
            _LOGGER.warning(f"Issue deleting file {path}, caused by {execinfo}")
            Path(path).chmod(stat.S_IWRITE)
            func(path)

        # Default output folder is "cdk.out"
        _LOGGER.debug("cleaning up %s %s", appdir, "cdk.out")
        cdkout = os.path.join(appdir, "cdk.out")
        if Path(cdkout).is_dir():
            shutil.rmtree(cdkout, onerror=remove_readonly)
        if Path(cache_dir).is_dir():
            shutil.rmtree(cache_dir, onerror=remove_readonly)

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

            if not self.enable_cache or kwargs.get("use_cache", False):
                print("false cache")
                return func(self, **kwargs)

            print("using cache")
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
            print("using cache")
            return out

        return cache

    @_cache
    def synthesize(self) -> Dict[str, Any]:
        """Run cdk synthesize command."""
        cmd_args = parse_args("synth", self.appdir)
        output = self.execute_command("synth", *cmd_args).out
        return self._template_formatter(output)

    @_cache
    def deploy(self) -> str:
        """Run cdk deploy command."""
        cmd_args = parse_args("deploy", self.appdir)
        return self.execute_command("deploy", *cmd_args).out

    @_cache
    def destroy(self) -> str:
        """Run cdk destroy command."""
        cmd_args = parse_args("destroy", self.appdir)
        return self.execute_command("destroy", *cmd_args).out

    def execute_command(self, cmd: str, *cmd_args) -> None:
        """Run arbitrary CDK command."""
        _LOGGER.debug([cmd, cmd_args])
        self.binary.append(cmd)
        cmdline = self.binary
        cmdline.extend(cmd_args)
        _LOGGER.info(cmdline)
        retcode, full_output_lines = None, []
        try:
            stderr_mode = subprocess.STDOUT if os.name == "nt" else subprocess.PIPE
            p = subprocess.Popen(
                cmdline,
                stdout=subprocess.PIPE,
                stderr=stderr_mode,
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
        return CDKCommandOutput(retcode, full_output, err)
