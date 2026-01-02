# Commissions Module

Staff commission tracking and payout management for service-based and sales businesses.

## Features

- Commission rate configuration
- Sales-based commission calculation
- Service-based commission tracking
- Commission reports
- Payout management
- Integration with Sales and Staff modules

## Installation

This module is installed automatically when activated in ERPlora Hub.

### Dependencies

- ERPlora Hub >= 1.0.0
- Required: `sales` >= 1.0.0
- Optional: `staff` for employee management

## Configuration

Access module settings at `/m/commissions/settings/`.

### Available Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `default_rate` | decimal | `0.10` | Default commission rate (10%) |
| `calculate_on` | string | `"net"` | Calculate on net or gross |
| `payout_frequency` | string | `"monthly"` | Payout frequency |

## Usage

### Views

| View | URL | Description |
|------|-----|-------------|
| Overview | `/m/commissions/` | Dashboard |
| Earnings | `/m/commissions/earnings/` | Commission earnings |
| Payouts | `/m/commissions/payouts/` | Payout history |
| Settings | `/m/commissions/settings/` | Module configuration |

### Commission Types

- **Flat Rate**: Fixed percentage on all sales
- **Tiered**: Different rates by sales volume
- **Product-Based**: Different rates per product/category
- **Service-Based**: Commission per service performed

## Permissions

| Permission | Description |
|------------|-------------|
| `commissions.view_commission` | View commissions |
| `commissions.manage_rates` | Manage commission rates |
| `commissions.process_payouts` | Process payouts |
| `commissions.view_reports` | View commission reports |

## Module Icon

Location: `static/icons/icon.svg`

Icon source: [React Icons - Ionicons 5](https://react-icons.github.io/react-icons/icons/io5/)

---

**Version:** 1.0.0
**Category:** services
**Author:** ERPlora Team
