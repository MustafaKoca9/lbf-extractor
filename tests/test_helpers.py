import importlib.util
import sys
import types
import unittest
from pathlib import Path

# Unit tests for pure helpers must also run before the optional dependency is installed.
# The fake cipher is never invoked by these tests.
fake_aes = types.SimpleNamespace(block_size=16, MODE_ECB=1)
fake_aes.new = lambda *args, **kwargs: None
fake_crypto = types.ModuleType("Crypto")
fake_cipher = types.ModuleType("Crypto.Cipher")
fake_cipher.AES = fake_aes
sys.modules.setdefault("Crypto", fake_crypto)
sys.modules.setdefault("Crypto.Cipher", fake_cipher)

MODULE_PATH = Path(__file__).resolve().parents[1] / "lbf_extractor.py"
SPEC = importlib.util.spec_from_file_location("lbf_extractor", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class PaddingTests(unittest.TestCase):
    def test_removes_valid_pkcs7_padding(self):
        self.assertEqual(MODULE.LBFExtractor.strip_pkcs7_padding(b"data\x04\x04\x04\x04"), b"data")

    def test_keeps_invalid_padding(self):
        self.assertEqual(MODULE.LBFExtractor.strip_pkcs7_padding(b"data\x02\x03"), b"data\x02\x03")

    def test_empty_input(self):
        self.assertEqual(MODULE.LBFExtractor.strip_pkcs7_padding(b""), b"")


if __name__ == "__main__":
    unittest.main()
