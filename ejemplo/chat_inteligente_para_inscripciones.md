# Documento de Proyecto: Chat Inteligente para Inscripciones (CII)
**Clave del Proyecto:** PRJ-DGSE-2026-04  
**Área Responsable:** Dirección General de Servicios Escolares & Dirección General de Tecnologías de Información  
**Versión:** 1.0  
**Fecha:** Octubre de 2026  
**Presupuesto:1000000**
**Costo real: 30000**
**Director de proyecto: Juan Torres**
**Fecha inicio: 2026-10-01**
**Fecha termino: 2027-01-31**

---

<!-- PÁGINA 1: CONTEXTO, CASO DE NEGOCIO Y OBJETIVOS -->

## 1. Resumen Ejecutivo y Caso de Negocio

El proceso anual de reinscripciones e ingreso en la universidad moviliza a una población de más de 85,000 estudiantes en un lapso crítico de cuatro semanas. Históricamente, las ventanillas de Servicios Escolares, la mesa de ayuda y las líneas telefónicas experimentan una sobrecarga operativa de hasta un 420% respecto a periodos regulares. 

El 73% de las incidencias reportadas corresponden a consultas repetitivas de baja complejidad cognitiva (requisitos documentales, emisión y cotejo de fichas de pago, compatibilidad de seriación en asignaturas y fechas de corte). Esta congestión genera tiempos de respuesta de hasta 72 horas, rezagos en trámites y una tasa de fricción del 14% por errores en la carga de documentación.

El proyecto **«Chat Inteligente para Inscripciones» (CII)** implementa un asistente conversacional multicanal sustentado en modelos de lenguaje natural (LLM) con arquitectura de Recuperación Aumentada por Generación (RAG). El sistema centraliza y personaliza la atención del alumnado, integrándose con el ecosistema universitario para proporcionar resoluciones contextuales y verificadas sin sobrecargar al personal administrativo.

```
[ Alumno / Aspirante ]
          │ (Consulta en lenguaje natural vía Portal / App)
          ▼
┌────────────────────────────────────────────────────────┐
│  CII Gateway (API Manager & Sanitización PII)          │
└────────────────────────┬───────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────┐
│  Capa Orquestadora RAG & Validación Semántica          │
│  ├── Base de Conocimiento Normativa (Vector DB)        │
│  └── Conectores Escolares (SISE Core / Pagos)          │
└────────────────────────┬───────────────────────────────┘
                         ▼
[ Respuesta Verificada + Trazabilidad en Logs ]
```

---

## 2. Objetivos del Proyecto

### 2.1 Objetivo General
Desarrollar, validar y poner en producción un agente conversacional basado en inteligencia artificial que ofrezca orientación personalizada, precisa e inmediata en lenguaje natural a la comunidad estudiantil durante el ciclo de inscripciones, asegurando estándares estrictos de gobernanza, privacidad y continuidad operativa.

### 2.2 Objetivos Específicos y Métricas de Éxito
* **Disponibilidad y Concurrencia:** Proveer atención continua (24/7) con capacidad de absorber al menos 1,200 sesiones concurrentes sin degradación del tiempo de respuesta (p95 < 1.8 segundos).
* **Eficiencia Operativa:** Reducir un 65% el volumen de solicitudes de primer nivel en ventanillas físicas y tickets de soporte técnico durante los primeros 15 días del proceso.
* **Resolución al Primer Contacto (FCR):** Alcanzar una tasa de resolución autónoma superior al 80% en consultas normativas, de calendario y aranceles.
* **Precisión y Seguridad:** Mantener una tasa de alucinación y desvío de contexto inferior al 0.5%, asegurando la neutralidad de datos sensibles y cumplimiento de la Ley General de Protección de Datos Personales.

---

## 3. Alcance Funcional

| Módulo | Capacidades Clave | Fuente de Verdad |
| :--- | :--- | :--- |
| **Normativa y Trámites** | Guía de requisitos, lineamientos de ingreso y validación de certificados | Reglamento General de Inscripciones |
| **Calendario y Turnos** | Notificación de citas asignadas, fechas límite y periodos extraordinarios | Cronograma Institucional Vigente |
| **Oferta Académica** | Horarios, sedes, cupos disponibles y revisión de seriación de planes de estudio | Catálogo Curricular Central |
| **Finanzas Escolares** | Generación y verificación de líneas de captura, costos y estados de pago | Módulo de Tesorería Escolar |
| **Escalamiento Humano** | Transferencia fluida del contexto de la conversación a operadores humanos para casos complejos | Plataforma de Mesa de Ayuda CRM |

---

<!-- PÁGINA 2: ARQUITECTURA, DATOS Y GOBERNANZA DE IA -->

## 4. Arquitectura Técnica e Integración

La solución se estructura sobre un diseño modular desacoplado que privilegia el control institucional de la información frente a modelos propietarios externos:

1. **Capa de Presentación:**
   * Widget embebido en el Portal Universitario de Alumnos y componente nativo en la aplicación móvil institucional.
   * Interfaz accesible bajo normas WCAG 2.1 nivel AA.

2. **Capa de Orquestación y RAG (Retrieval-Augmented Generation):**
   * **Vector Store:** Base de datos vectorial con control de acceso basado en roles (RBAC) para el indexado de reglamentos, manuales y acuerdos de consejo técnico.
   * **Embeddings & LLM:** Empleo de modelos de lenguaje ajustados al dominio universitario y dialecto institucional, alojados en infraestructura privada/nube soberana.
   * **Guardrails Semánticos:** Filtros de preprocesamiento (detección de prompt injection, lenguaje inapropiado y exfiltración de credenciales) y postprocesamiento (verificación cruzada de hechos).

3. **Capa de Integración con Sistemas Legados:**
   * Conectores seguros vía API REST / GraphQL hacia el Sistema Integral de Servicios Escolares (SISE) y pasarelas de pago.
   * Mecanismo de autenticación federada (OAuth 2.0 / SAML) para consultas que involucren el historial académico particular del alumno.

---

## 5. Marco de Gobernanza de IA, Seguridad y Privacidad

Para garantizar un despliegue ético y transparente, el proyecto se rige por un marco de gobernanza institucional de IA que establece:

```
[ Principios Rectores de Gobernanza de IA ]
├── Privacidad por Diseño (Anonimización de PII, cero retención de tokens privados)
├── Explicabilidad y Atribución (Cita explícita del artículo/reglamento fuente)
├── Supervisión Humana (Human-in-the-Loop para casos de bloqueo de trámite)
└── Auditoría Continua (Monitoreo de drift, sesgo en respuestas y tasa de fallback)
```

* **Privacidad y Protección de Datos:** Implementación de técnicas de tokenización y anonimización de Datos Personales Identificables (PII) antes de su procesamiento por el modelo. En ningún caso los historiales de conversación se emplean para el reentrenamiento de modelos sin un proceso previo de disociación irreversible.
* **Transparencia Activa:** El sistema informa de manera explícita al usuario desde el primer mensaje que está interactuando con un asistente de inteligencia artificial. Cada respuesta normativa incluye la referencia reglamentaria exacta que sustenta la información entregada.
* **Protocolo de Falla Segura y Escalamiento:** Si la métrica de confianza de la respuesta calculada cae por debajo del umbral del 85%, el sistema no realiza conjeturas; emite un mensaje delimitador y ofrece la canalización prioritaria con un funcionario de ventanilla digital.
* **Comité de Ética y Seguimiento:** Órgano colegiado conformado por la Defensoría de los Derechos Universitarios, la Dirección Jurídica y expertos de cómputo, con facultades para auditar periódicamente los registros del sistema.

---

<!-- PÁGINA 3: PLAN DE IMPLEMENTACIÓN, RIESGOS Y OPERACIÓN -->

## 6. Fases de Implementación y Cronograma

El despliegue se programó en cuatro etapas secuenciales abarcando un ciclo total de 24 semanas:

```
Semana 01-06   [■■■■■■] Fase 1: Arquitectura, curaduría de datos y gobernanza
Semana 07-12            [■■■■■■] Fase 2: Configuración RAG, APIs y Guardrails
Semana 13-18                     [■■■■■■] Fase 3: Pruebas piloto (Facultad muestra)
Semana 19-24                              [■■■■■■] Fase 4: Despliegue general y monitoreo
```

1. **Fase 1: Preparación y Curaduría de Datos (Semanas 1-6)**
   * Homologación y limpieza documental de reglamentos, preguntas frecuentes y catálogos de materias.
   * Formalización del protocolo ético y términos de servicio del asistente.
2. **Fase 2: Construcción e Integración Técnica (Semanas 7-12)**
   * Despliegue de la infraestructura vectorial y conectores seguros hacia el SISE.
   * Configuración de microservicios de anonimización y pruebas de resistencia de infraestructura.
3. **Fase 3: Piloto Controlado (Semanas 13-18)**
   * Puesta en marcha en dos facultades seleccionadas (muestra de 8,000 estudiantes).
   * Evaluación de métricas de precisión semántica, calibración de prompts y corrección de desvíos informativos.
4. **Fase 4: Despliegue General y Soporte Crítico (Semanas 19-24)**
   * Lanzamiento para toda la comunidad universitaria sincronizado con el inicio formal del periodo de inscripciones.
   * Turnos de monitoreo en tiempo real por el equipo de ingeniería y operadores de enlace.

---

## 7. Matriz de Gestión de Riesgos

| Riesgo Identificado | Severidad | Probabilidad | Estrategia de Mitigación |
| :--- | :---: | :---: | :--- |
| **Alucinación o referencia normativa obsoleta** | Alta | Baja | Arquitectura RAG estricta con prohibición de generación libre; indexación obligatoria con fecha de vigencia por documento. |
| **Saturación de servicios escolares centrales (APIs)** | Alta | Media | Capa intermedia de caché distribuida para consultas estáticas (horarios/planes) y rate limiting por cuenta de alumno. |
| **Intentos de inyección de instrucciones (Jailbreak)** | Media | Alta | Sanitización de entradas con modelos clasificadores perimetrales y restricción del system prompt a funciones estrictamente escolares. |
| **Resistencia al cambio del personal administrativo** | Media | Media | Talleres de capacitación previa, reorientando el rol del personal hacia la atención de casos especiales de alto valor humano. |

---

## 8. Estrategia de Monitoreo y Retorno de Inversión

El desempeño del sistema se mide a través de un panel de observabilidad centralizado que audita:

* **Tasa de transferencia a humanos:** Umbral operativo máximo permitido del 18%.
* **Índice de satisfacción estudiantil (CSAT):** Evaluación rápida obligatoria post-interacción (escala 1 a 5 estrellas, meta institucional $\ge$ 4.3).
* **Tiempos de espera globales:** Reducción proyectada de colas físicas de 45 minutos promedio a menos de 5 minutos para trámites presenciales que requieran firma física.

El proyecto consolida la modernización administrativa universitaria al transformar un cuello de botella recurrente en un proceso de autoatención seguro, auditable y centrado en la experiencia del estudiante.