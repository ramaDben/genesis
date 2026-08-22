# Datos de FTMO y respaldos en GitHub

## El dataset es irrepetible

El export se hizo con una cuenta de prueba de FTMO **ya expirada**. No se puede regenerar: los
brokers sirven historial de ticks en ventana móvil, así que una cuenta nueva daría otra
profundidad y otro `dataset_hash`, invalidando comparaciones con artefactos previos.

Está archivado en el release privado **`dataset-ftmo-2026-08-01`** de `ramaDben/genesis`:
9 assets, 1,21 GB — ocho símbolos (EURUSD, GBPUSD, GER40.cash, US100.cash, US30.cash,
US500.cash, USDJPY, XAUUSD) más CSV y manifest.

```bash
gh release download dataset-ftmo-2026-08-01 -R ramaDben/genesis -D /tmp/ds
for f in /tmp/ds/*.tar.gz; do tar -xzf "$f"; done   # recrea data/ en la raíz
```

Los release assets admiten **2 GB cada uno** — el límite de 100 MB aplica a archivos dentro del
repo, no a los assets. (Creencia errónea que casi provoca descartar el dataset.)

## Release `archive-2026-07-28`

Artefactos fuera de control de versiones: `.pulse/` completo (100 documentos del ciclo SDD de
doce changes), los artefactos de la corrida D (`out/run_d/` con `history_depth.json`,
`m1_edge.json`, `ftmo.json`) y las memorias de Claude Code (`genesis-claude-memory-*.tar.gz`).

El cuerpo de ese release contiene la guía de recuperación post-formateo, pero fue escrito
**antes** de la migración a WSL2: sus pasos asumen Windows y dicen 640 tests. Preferir el README
del repo, que sí está al día.

## Reloj del servidor de FTMO

Es **NY+7 con regla DST de EE.UU.** — no equivale a `Europe/Athens`, que diverge una hora en las
ventanas de transición. Decisión tomada: **excluir del análisis** los días de servidor
2025-10-26→11-02 y 2026-03-08→03-29.

Bordes M1 originales: índices desde 10-22, GER40 10-13, XAUUSD 10-29, majors 11-05.

Ver también `mem:entorno-de-desarrollo`.
