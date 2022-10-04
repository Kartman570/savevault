import fnmatch
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile


def snapshot(source, vault, label="", exclude=()):
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
                if any(fnmatch.fnmatch(relative, pattern) for pattern in exclude):
                    continue
                content = path.read_bytes()
                output.writestr("files/" + relative, content)
                files[relative] = {"sha256": hashlib.sha256(content).hexdigest(),
                                   "size": len(content)}
            output.writestr("manifest.json", json.dumps({"label": label, "files": files}))
        destination = vault / (identifier + ".zip")
        os.link(archive, destination)
    return identifier


def archive_path(vault, identifier):
    if not identifier.isdigit() or len(identifier) != 6:
        raise ValueError("Snapshot ID must contain six digits")
    return Path(vault) / (identifier + ".zip")


def manifest(vault, identifier):
    with zipfile.ZipFile(archive_path(vault, identifier)) as archive:
        return json.loads(archive.read("manifest.json"))


def list_snapshots(vault):
    result = []
    for path in sorted(Path(vault).glob("*.zip")):
        if len(path.stem) != 6 or not path.stem.isdigit():
            continue
        data = manifest(vault, path.stem)
        result.append({"id": path.stem, "label": data["label"],
                       "files": len(data["files"]),
                       "bytes": sum(item["size"] for item in data["files"].values())})
    return result


def verify(vault, identifier):
    with zipfile.ZipFile(archive_path(vault, identifier)) as archive:
        data = json.loads(archive.read("manifest.json"))
        if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
            raise ValueError("Invalid archive manifest")
        expected = {"manifest.json"}
        for name, info in data["files"].items():
            path = Path(name)
            if (not name or path.is_absolute() or "\\" in name
                    or any(part in ("", ".", "..") for part in name.split("/"))):
                raise ValueError("Unsafe file name in archive")
            if (not isinstance(info, dict) or type(info.get("size")) is not int
                    or info["size"] < 0 or not isinstance(info.get("sha256"), str)):
                raise ValueError("Invalid file metadata: " + name)
            member = "files/" + name
            expected.add(member)
            content = archive.read(member)
            checksum = hashlib.sha256(content).hexdigest()
            if len(content) != info["size"] or checksum != info["sha256"]:
                raise ValueError("Checksum mismatch: " + name)
        if set(archive.namelist()) != expected or len(archive.namelist()) != len(expected):
            raise ValueError("Unexpected or duplicate archive entries")
    return data


def restore(vault, identifier, destination):
    data = verify(vault, identifier)
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("Restore destination must not exist")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as directory:
        staging = Path(directory) / "restored"
        staging.mkdir()
        with zipfile.ZipFile(archive_path(vault, identifier)) as archive:
            for name in data["files"]:
                target = staging / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read("files/" + name))
        staging.rename(destination)
    return len(data["files"])


def compare(vault, before, after):
    old = verify(vault, before)["files"]
    new = verify(vault, after)["files"]
    return {"added": sorted(new.keys() - old.keys()),
            "removed": sorted(old.keys() - new.keys()),
            "changed": sorted(name for name in old.keys() & new.keys()
                              if old[name] != new[name])}


def prune(vault, keep, apply=False):
    if keep < 1:
        raise ValueError("Keep at least one snapshot")
    snapshots = list_snapshots(vault)
    removed = [item["id"] for item in snapshots[:-keep]]
    if apply:
        for identifier in removed:
            archive_path(vault, identifier).unlink()
    return removed
