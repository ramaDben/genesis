# Gate 2 (Code-Quality) — Issue #18, change 18-docs-spec-firma-de-datos-alternativa-ftmo-ficha-candidata-cuenta

- Veredicto: `CODE_QUALITY: ✅`. Delta doc-only (`docs/SPEC_GENESIS_v1.3_PropTrading_TorneoCandidatos.md`), commit `97f173c` en rama `docs/18-spec-ftmo-firma-datos-alternativa`.
- Toolchain real: ruff check (2 errors, ambos en `out/run_d/probe_mt5.py` — ajeno al delta), ruff format --check (1 archivo, mismo script), ty check (10 diagnostics, mismo script, stubs `MetaTrader5` sin tipar), pytest (633 passed, 148s). `src/genesis/` y `tests/` limpios.
- PR creado: https://github.com/bbenja11/genesis/pull/19 (base main ← docs/18-spec-ftmo-firma-datos-alternativa), cuerpo con ambos veredictos (Gate 1 ✅ + Gate 2 ✅), Refs #18.
- Report: `.pulse/changes/18-docs-spec-firma-de-datos-alternativa-ftmo-ficha-candidata-cuenta/code_quality_report.md`.
- Nota reutilizable: cuando el hallazgo de ruff/ty/pytest está confinado a `out/run_d/probe_mt5.py` (script ad-hoc no commiteado), no cuenta contra el gate de ningún change — confirmar con `git show --stat <commit>` que el archivo no forma parte del delta auditado.
- Pendiente para el hilo principal: solo falta `request_sdd_transition` (no lo hace este subagente).
