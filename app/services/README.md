# Refind Cloud - Service Layer Architecture

This directory is designated for cross-cutting application services, external API integration wrappers, and shared utility managers.

## Purpose & Scope

Unlike domain modules in `app/modules/`, services in `app/services/` handle shared infrastructure tasks and external integrations, such as:

- External cloud provider API adapters (e.g., hypervisor APIs, Pterodactyl/Minecraft panel integrations)
- Notification and webhook dispatchers
- Metric collectors and telemetry
- Shared task queue execution wrappers

## Service Layer Rules

1. Services must consume configuration via `app.core.config.get_settings()` or `AppContext`.
2. Async operations must use `async`/`await` throughout.
3. Database sessions should be passed explicitly or acquired via `app.database.session.get_async_session()`.
4. No business logic should reside inside Discord cog handlers; cogs delegate work to services.
