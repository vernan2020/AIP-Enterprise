# AIP RC1 runtime checkpoint — 2026-08-29

This checkpoint preserves the recovered functional `src/` runtime tree used to restore AIP Enterprise RC1 after the Windows reboot/configuration incident.

- Archive: `runtime_src.tgz`, stored as ordered Base64 parts `runtime_src.partNN.b64`.
- SHA-256: `74bfaa04d2709ac903e4d315b46cf2c74e9aa62a7749286e0110c86fde11c6c4`
- Restore: `python scripts/recovery/restore_runtime_checkpoint.py`
- Secrets are **not** included.
- The launcher restores this checkpoint automatically only when critical recovered runtime files are missing.
