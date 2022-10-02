# savevault

Local snapshots for game saves and other small folders. Each ZIP contains its own
file manifest and SHA-256 checksums. Snapshots use increasing identifiers, so labels
can describe checkpoints without relying on filenames chosen by a game.

Requires Python 3.9 or newer; the application uses only the standard library.

```sh
mkdir -p /tmp/demo-save
printf 'level=3\n' > /tmp/demo-save/slot.txt
python3 savevault.py --vault /tmp/demo-vault backup /tmp/demo-save --label checkpoint
python3 savevault.py --vault /tmp/demo-vault list
python3 savevault.py --vault /tmp/demo-vault verify 000001
python3 savevault.py --vault /tmp/demo-vault restore 000001 /tmp/recovered-save
```

Use fresh directories for the example. Restore refuses any existing destination,
checks every archive entry, writes a staging directory and moves it into place.
Empty directories, permissions and symbolic links are not preserved. Symbolic links
in the source are rejected. Keep the vault outside the source tree.

```sh
python3 savevault.py --vault /tmp/demo-vault backup /tmp/demo-save --exclude '*.tmp'
python3 savevault.py --vault /tmp/demo-vault diff 000001 000002
python3 savevault.py --vault /tmp/demo-vault prune --keep 5
python3 savevault.py --vault /tmp/demo-vault prune --keep 5 --apply
```

Pruning only deletes when `--apply` is present. Archives are independent; keeping a
later archive does not require earlier ones. Checksums detect accidental damage,
not malicious replacement. Use this on your own small save files, with the game
closed: a snapshot is not a transaction across multiple changing files. Each file
is held in memory while being archived or verified. Do not run concurrent backup,
restore or cleanup processes against the same vault. This is a local convenience
tool, not a replacement for an off-device backup.

## Checks

```sh
python3 -m unittest discover -s tests -v
python3 -m pip install -r requirements-dev.txt
python3 -m flake8 .
```
