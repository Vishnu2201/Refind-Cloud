# Refind Cloud - Business Modules Architecture

This directory is reserved for domain-specific business modules. Modules in `app/modules/` represent clean, decoupled domain bounded contexts.

## Standard Module Layout

When business features are introduced in future phases, each module will follow a consistent structure:

```
app/modules/<module_name>/
├── __init__.py
├── models.py       # Domain-specific SQLAlchemy ORM models
├── schemas.py      # Pydantic request/response/validation schemas
├── services.py     # Domain business logic
└── cog.py          # Discord slash commands and event handlers
```

## Planned Modules Roadmap

The foundation is designed to incorporate the following modules without requiring structural refactoring:

1. **Server & Channel Management** (`app/modules/channels/`): Automated setup, categorization, and channel state management.
2. **Role & Permission Management** (`app/modules/roles/`): Dynamic role assignment, staff hierarchy, and permission checks.
3. **Ticket System** (`app/modules/tickets/`): Customer support ticket creation, transcript storage, and assignment lifecycle.
4. **Customer Management** (`app/modules/customers/`): Hosting account mapping, profile metadata, and customer verification.
5. **Manual Billing & Orders** (`app/modules/billing/`): Order tracking, manual invoice processing, and billing state.
6. **VPS Provisioning** (`app/modules/vps/`): Virtual Private Server integration with cloud hypervisors and status metrics.
7. **Minecraft Provisioning** (`app/modules/minecraft/`): Minecraft game server instance lifecycle, RCON management, and node metrics.
8. **Moderation** (`app/modules/moderation/`): Automated auto-mod rules, sanctions logging, warnings, mute/kick/ban tracking.
9. **Anti-Nuke & Security** (`app/modules/security/`): Guild raid defense, invite inspection, rate limiting, and permission guards.
10. **Audit Logging System** (`app/modules/audit/`): Administrative action recording, database activity logs, and Discord event logging.
11. **Community Features** (`app/modules/community/`): Giveaways, server reviews, invite tracking, and community engagements.

> [!NOTE]
> Foundation phase contains zero mock, seeded, or placeholder operational data. Modules will be implemented sequentially with real API and database integrations.
