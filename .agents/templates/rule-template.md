---
# YAML frontmatter — eliminar si la regla aplica a todos los archivos
# paths: lista de globs que activan esta regla (opcional)
# paths:
#   - "src/**/*.py"
#   - "tests/**/*.py"
---

<!--
  NOTAS DE MANTENIMIENTO (este bloque HTML se elimina del contexto de la IA,
  así que no consume tokens. Úsalo para dejar instrucciones a tu equipo.)

  Propósito de esta regla: <describir qué aspecto del proyecto cubre>
  Última revisión: <fecha>
  Dueño: <equipo o persona>

  Para forzar scope: agregar o modificar el campo `paths` en el frontmatter.
-->

# <Nombre de la Regla>

<!-- Ejemplo: "EDD (Eval-Driven Development) y TDD" -->
<!-- Máximo ~200 líneas por archivo. Si crece, dividir en archivos más específicos. -->

## Contexto del proyecto

<!-- ¿Qué parte del codebase cubre esta regla? ¿Por qué existe en el contexto de genesis? -->

[Explicación de por qué existe la regla y qué problema resuelve]

## Reglas principales

<!-- Sé específico y verificable. Prefiere frases del tipo "siempre X" o "nunca Y". -->

- **Obligatorio**: [Regla 1]
- **Prohibido**: [Regla 2]
- **Convención**: [Regla 3]

## Antipatrones y Restricciones

<!-- Enumera los anti-patrones específicos de este módulo. -->

- [Antipatrón 1]
- [Antipatrón 2]

## Patrones requeridos

<!-- Muestra el patrón correcto vs incorrecto cuando la regla no es obvia. -->

```python
# ✅ Correcto
def mi_funcion():
    pass

# ❌ Incorrecto
def miFuncion():
    pass
```

## Convenciones de nomenclatura

<!-- Solo si aplica al scope de esta regla. Eliminar si no es relevante. -->

| Elemento   | Patrón           | Ejemplo           |
| ---------- | ---------------- | ----------------- |
| Clases     | PascalCase       | `WorkflowEngine`  |
| Variables  | snake_case       | `project_state`   |
| Constantes | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |

## Referencias

<!-- Links a documentación interna, Issues, PRs o documento de diseño relacionado -->

- [Enlace a Issue o PR]
- [Enlace a otras reglas]
