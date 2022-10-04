import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from vault import compare, list_snapshots, prune, restore, snapshot, verify


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "saves"
        self.source.mkdir()
        self.vault = self.root / "vault"
        (self.source / "slot.dat").write_bytes(b"level=3\x00health=8")

    def test_roundtrip(self):
        identifier = snapshot(self.source, self.vault, "before boss")
        target = self.root / "restored"
        self.assertEqual(restore(self.vault, identifier, target), 1)
        self.assertEqual((target / "slot.dat").read_bytes(),
                         (self.source / "slot.dat").read_bytes())
        self.assertEqual(list_snapshots(self.vault)[0]["label"], "before boss")

    def test_refuse_existing_destination(self):
        identifier = snapshot(self.source, self.vault)
        with self.assertRaises(ValueError):
            restore(self.vault, identifier, self.source)
        self.assertTrue((self.source / "slot.dat").exists())

    def test_exclusions_and_diff(self):
        first = snapshot(self.source, self.vault)
        (self.source / "slot.dat").write_text("changed")
        (self.source / "cache.tmp").write_text("skip")
        (self.source / "settings.ini").write_text("volume=2")
        second = snapshot(self.source, self.vault, exclude=["*.tmp"])
        self.assertEqual(compare(self.vault, first, second),
                         {"added": ["settings.ini"], "removed": [], "changed": ["slot.dat"]})

    def test_prune_preview(self):
        for _ in range(3):
            snapshot(self.source, self.vault)
        self.assertEqual(prune(self.vault, 1), ["000001", "000002"])
        self.assertEqual(len(list_snapshots(self.vault)), 3)
        prune(self.vault, 1, apply=True)
        self.assertEqual(len(list_snapshots(self.vault)), 1)

    def test_nested_vault_rejected(self):
        with self.assertRaises(ValueError):
            snapshot(self.source, self.source / "vault")

    def test_links_rejected(self):
        (self.source / "link").symlink_to(self.source / "slot.dat")
        with self.assertRaises(ValueError):
            snapshot(self.source, self.vault)

    def test_tampered_content(self):
        self.vault.mkdir()
        info = {"label": "", "files": {"slot": {"size": 1, "sha256": "bad"}}}
        with zipfile.ZipFile(self.vault / "000001.zip", "w") as archive:
            archive.writestr("manifest.json", json.dumps(info))
            archive.writestr("files/slot", b"x")
        with self.assertRaises(ValueError):
            verify(self.vault, "000001")

    def test_path_traversal(self):
        self.vault.mkdir()
        info = {"label": "", "files": {"../outside": {
            "size": 1, "sha256": hashlib.sha256(b"x").hexdigest()}}}
        with zipfile.ZipFile(self.vault / "000001.zip", "w") as archive:
            archive.writestr("manifest.json", json.dumps(info))
            archive.writestr("files/../outside", b"x")
        with self.assertRaises(ValueError):
            restore(self.vault, "000001", self.root / "restored")
        self.assertFalse((self.root / "outside").exists())

    def test_invalid_manifest_shape(self):
        self.vault.mkdir()
        with zipfile.ZipFile(self.vault / "000001.zip", "w") as archive:
            archive.writestr("manifest.json", json.dumps({"files": []}))
        with self.assertRaises(ValueError):
            verify(self.vault, "000001")

    def test_partial_backup_not_published(self):
        (self.source / "link").symlink_to(self.source / "slot.dat")
        with self.assertRaises(ValueError):
            snapshot(self.source, self.vault)
        self.assertEqual(list(self.vault.iterdir()), [])
