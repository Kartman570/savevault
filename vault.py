import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def snapshot(source, vault, label=""):
    source, vault = Path(source).resolve(), Path(vault).resolve()
    if not source.is_dir():
        raise ValueError("Source must be a directory")
    if source == vault or source in vault.parents:
        raise ValueError("Vault must be outside the source directory")
    vault.mkdir(parents=True, exist_ok=True)
    numbers = [int(path.stem) for path in vault.glob("*.zip") if path.stem.isdigit()]
    identifier = "{:06d}".format(max(numbers, default=0) + 1)
    files = {}
    with tempfile.TemporaryDirectory(dir=vault) as directory:
        archive = Path(directory) / "snapshot.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
            for path in sorted(source.rglob("*")):
                if path.is_symlink():
                    raise ValueError("Symbolic links are not supported: " + str(path))
                if not path.is_file():
                    continue
                relative = path.relative_to(source).as_posix()
                output.write(path, "files/" + relative)
                files[relative] = {"sha256": digest(path), "size": path.stat().st_size}
            output.writestr("manifest.json", json.dumps({"label": label, "files": files}))
        destination = vault / (identifier + ".zip")
        with destination.open("xb") as target, archive.open("rb") as data:
            shutil.copyfileobj(data, target)
    return identifier
