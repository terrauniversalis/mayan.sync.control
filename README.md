# Mayan Sync Control

Mayan Sync Control es un módulo de registro y ruteo de controladores MIDI diseñado para trabajar en conjunto con Mayan Sync y Mayan Mappings. Su propósito es detectar, validar y compartir controladores físicos (USB, Bluetooth, Wi‑Fi, LAN y dispositivos offline) entre múltiples máquinas, permitiendo que los instrumentos y superficies de control se utilicen dentro de un flujo centralizado de sincronización musical.

## Inicio rápido

1. Instala el entorno en modo editable:

   ```bash
   pip install -e .
   ```

2. Crea un archivo `config.json` con los hosts y dispositivos iniciales que quieras monitorear:

   ```json
   {
     "inventory": {"path": "inventory.json"},
     "hosts": [
       {"id": "house", "label": "House Main", "priority": 50},
       {"id": "ipad", "label": "iPad", "priority": 10}
     ],
     "seed_devices": [
       {
         "vendor": "Pioneer",
         "product": "DDJ-REV1",
         "connection": "usb",
         "metadata": {"routing_mode": "primary"}
       },
       {
         "vendor": "Akai",
         "product": "APC40",
         "connection": "lan",
         "metadata": {"routing_mode": "mirror", "preferred_host": "ipad"}
       }
     ]
   }
   ```

3. Ejecuta el agente en modo demostración (utiliza un monitor interno que emite los dispositivos configurados en `seed_devices`):

   ```bash
   mayan-sync-agent config.json
   ```

El agente registra cada controlador en el inventario (generando un U-SHA estable), aplica las reglas de ruteo por prioridad y deja el estado persistido en `inventory.json`. Esta base puede ampliarse con monitores reales para MIDI 2.0, OSC, Bluetooth o LAN.

## Objetivos

- **Descubrimiento automático:** detectar cualquier controlador conectado a una máquina compatible (Windows, macOS, iPadOS, Android, Linux) ya sea por USB, LAN, Bluetooth o modo offline.
- **Registro único universal (U-SHA):** generar una huella digital única combinando número de serie, fabricante, identificadores USB/MIDI y metadatos definidos por el inventario de audio.
- **Ruteo multi-dispositivo:** permitir que un controlador se enrute a uno o varios hosts Mayan Sync simultáneamente, con control de prioridad y reserva.
- **Integración con Mayan Mappings:** entregar un flujo MIDI limpio y normalizado que pueda mapearse de forma consistente en distintos escenarios.
- **Experiencia de usuario simple:** mostrar en la barra de tareas un icono minimalista con el número de controladores activos y un selector rápido de host/escena.

## Arquitectura Propuesta

### 1. Agente de Controlador

- Servicio residente en cada máquina (PC, Surface Duo, iPad mediante bridge LAN, etc.).
- Implementa autoarranque y sandbox según plataforma (por ejemplo, Launch Agent en macOS, servicio en Windows, demonio en Linux).
- Captura eventos de conexión/desconexión de dispositivos MIDI, HID y OSC.
- Lee metadatos (fabricante, ID de dispositivo, interfaz, número de serie cuando sea posible) y construye un `DeviceDescriptor` estandarizado.

### 2. Inventario y Validación

- Sincroniza el `DeviceDescriptor` con el módulo de **Inventario de Audio** de Mayan.
- Combina el descriptor con información del catálogo (modelo aprobado, perfil recomendado, estado de mantenimiento) para generar la huella `U-SHA`.
- Si el dispositivo no está en inventario, crea una entrada provisional con estado `pending-validation`.
- Los perfiles aprobados disparan descarga automática de firmware o plantillas cuando existan.

### 3. Registro en Mayan Sync

1. El agente envía el `U-SHA` junto con el estado de conexión al nodo maestro Mayan Sync.
2. El maestro verifica duplicados y aplica políticas de prioridad (ej. reservar para escenario «House Main», liberar para «Studio B»).
3. Se actualiza la matriz de ruteo MIDI para exponer el dispositivo a los hosts autorizados.

### 4. Mayan Sync Flow

- Cada host ejecuta un **Mayan Sync Router** que expone puertos virtuales MIDI 2.0 (preview 13.192) y OSC.
- Los controladores físicos se asignan a estos puertos virtuales mediante reglas de `RoutingPolicy`.
- El router soporta **multi-cast** (duplicar flujo a varias máquinas) y **failover** (si un host cae, se reasigna al siguiente).
- El usuario puede seleccionar desde la UI qué host recibe la señal principal y cuáles la reciben en modo espejo.

### 5. Integración con Mayan Mappings

- Cada `U-SHA` se asocia a una plantilla de mapeo (`MappingProfile`).
- Cuando un dispositivo se activa, el router notifica a Mayan Mappings para precargar el perfil.
- Las configuraciones manuales se sincronizan con el repositorio central para garantizar consistencia entre máquinas.

### 6. UI y Tray Icon

- Icono persistente que muestra conteo de controladores activos y estado de red (LAN, Wi-Fi, Bluetooth, Offline).
- Menú contextual con acciones rápidas:
  - Seleccionar host o escena (House, Mini Ómsi, iPad, etc.).
  - Forzar validación/inventario.
  - Diagnóstico rápido (latencia, firmware, señal).
  - Modo offline: registra la actividad para sincronizar cuando vuelva la conexión.

## Detección de Nuevos Instrumentos

- **Hot Plug Listener:** monitor de eventos del sistema operativo (`udev`, `IOKit`, `SetupAPI`).
- **Discovery Broadcast:** para dispositivos en red, se realiza broadcast mDNS/OSC y ARP para detectar hubs tipo HP Traveller o Surface Duo.
- **Prioridad de Atención:** se aplica cola de prioridad basada en tipo de evento (nuevo controlador vs. reconexión) y en la demanda de escenas activas.
- **Notificación:** se muestra alerta en la UI y se envía webhook/OSC a Mayan Sync para actualización inmediata.

## Seguridad y Privacidad

- Comunicación cifrada (TLS mutuamente autenticado) entre agentes y el maestro.
- El `U-SHA` evita almacenar seriales en texto plano, pero permite rastreo confiable.
- Registro de auditoría para cada conexión/desconexión y cambios de ruteo.
- Opciones de aislamiento para evitar que un controlador no autorizado se inyecte en el flujo.

## Flujo de Implementación

1. **Prototipo de Agente**
   - Construir un servicio cross-platform (Rust, Go o Node.js con bindings nativos).
   - Integrar librerías MIDI 2.0 y detección de hardware (ej. `rtmidi`, `CoreMIDI`, `WinMM`).

2. **API del Maestro Mayan Sync**
   - REST/gRPC para registrar dispositivos y consultar rutas activas.
   - WebSockets/OSC para notificaciones en tiempo real.

3. **Módulo de Inventario**
   - Base de datos central (PostgreSQL) con tabla `audio_devices` y campo `u_sha`.
   - Integración con inventario existente (importaciones CSV/API externa).

4. **UI Tray y Panel de Control**
   - Electron/Tauri para escritorio; aplicación companion en iPad vía LAN.
   - Componentes mínimos: lista de controladores, selector de host, estado de sincronización.

5. **Mayan Mappings Integration**
   - Definir formato de perfil (`.mayanmap` JSON/YAML).
   - Automatizar carga/descarga en función del `U-SHA`.

6. **Pruebas y Validación**
   - Escenarios con múltiples controladores y hosts (Djay Pro, Mini Ómsi, iPad).
   - Validar latencia, reconexión automática y consistencia de mappings.

## Consideraciones Adicionales

- Documentar procedimiento para añadir nuevos tipos de dispositivos (por ejemplo, controladores DJ propietarios o superficies táctiles personalizadas).
- Preparar modo de mantenimiento para actualizar firmware sin afectar el flujo en vivo.
- Incluir métricas (Prometheus/Grafana) para monitoreo del ecosistema Mayan.
- Diseñar opciones de escalado horizontal para el maestro (cluster activo/pasivo).

---

Esta guía establece el primer paso para que Mayan Sync Control actúe como puerta de entrada antes del mapeo: detectar, validar y enrutar controladores MIDI de forma confiable en un entorno multi-plataforma y multi-escena.
