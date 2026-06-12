---
# FRONTMATTER - Configuración del skill
# =====================================

# name (Opcional)
# Nombre para mostrar del skill. Si se omite, utiliza el nombre del directorio.
name: mi-skill-template

# description (Recomendado)
# Qué hace el skill y cuándo usarlo. La IA utiliza esto para decidir cuándo aplicar el skill.
description: Plantilla de skill para ejecutar flujos de trabajo específicos.

# when_to_use (Opcional)
# Contexto adicional para cuándo la IA debe invocar el skill.
when_to_use: Úsalo cuando...

# argument-hint (Opcional)
# Sugerencia mostrada durante el autocompletado para indicar argumentos esperados.
argument-hint: "[archivo] [formato]"

# arguments (Opcional)
# Argumentos posicionales nombrados para sustitución de $name en el contenido del skill.
arguments: [archivo, formato]

# disable-model-invocation (Opcional)
# Establezca en true para evitar que se cargue automáticamente este skill.
disable-model-invocation: false

# user-invocable (Opcional)
# Establezca en false para ocultar del menú /.
user-invocable: true

# allowed-tools (Opcional)
# Herramientas que se pueden usar sin pedir permiso cuando este skill está activo.
allowed-tools: Read Grep

# effort (Opcional)
# Nivel de esfuerzo cuando este skill está activo.
# effort: high

# context (Opcional)
# Establezca en fork para ejecutar en un contexto de subagent bifurcado.
# context: fork

---

## Tipos de Context Injection (Inyección de Contexto)

La inyección de contexto permite ejecutar comandos y cargar archivos dinámicamente en el skill antes de procesarlo.

### 1. Bash Command Injection - Inyección de Comando Bash

Ejecuta un comando bash y reemplaza la línea con su salida. Usa la sintaxis `!`comando``

```markdown
## Cambios actuales en el repositorio

!`git diff HEAD`
```

### 2. File Injection - Inyección de Archivo

Carga el contenido de un archivo directamente en el skill. Usa la sintaxis `@archivo`

```markdown
## Archivo de configuración

@pyproject.toml
```

### 3. Directory Listing Injection - Inyección de Listado de Directorio

Lista el contenido de un directorio. Usa la sintaxis `@directorio/`

```markdown
## Estructura del proyecto

@src/pulse/
```

### 4. String Substitution - Sustitución de Cadenas

Reemplaza variables dinámicas en el contenido del skill.

- `$ARGUMENTS` - Todos los argumentos pasados al invocar el skill
- `$ARGUMENTS[N]` o `$N` - Argumento específico por índice
- `$nombre` - Argumento nombrado declarado en frontmatter
- `${CLAUDE_SESSION_ID}` - ID de sesión actual

## Instrucciones del Skill

1. [Paso 1 del skill]
2. [Paso 2 del skill]
3. [Restricciones o formato de salida]
