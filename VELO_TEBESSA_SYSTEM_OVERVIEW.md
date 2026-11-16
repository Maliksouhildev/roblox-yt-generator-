# Velo Tebessa — Complete System Architecture & Operational Blueprint

## 1. System Overview & Real-World Operating Environment

### 1.1 Purpose and Scope
Velo Tebessa is a unified B2C and B2B bicycle parts e-commerce storefront combined with an integrated ERP, WMS, CRM, and SCF-compliant accounting engine built specifically for the Algerian commercial landscape. It bridges online storefront sales, physical showroom point-of-sale (POS) operations, call center order confirmation, national and local courier delivery, and strict partnership financial accounting.

### 1.2 Target Operational Realities in Algeria
- **Mobile Network Latency:** 80%+ of users access the platform over Algerian 4G networks (Mobilis, Djezzy, Ooredoo) with typical round-trip latencies between 150ms and 300ms. All public pages must achieve complete visual load under 2 seconds.
- **In-App Social WebViews:** Most inbound storefront traffic originates from Instagram, Facebook, and TikTok advertisements. These platforms open links inside restricted in-app WebViews that isolate local storage and cookies from the main browser and block standard Google OAuth authentication.
- **Carrier-Grade NAT (CGNAT):** Thousands of mobile mobile users share a single public IPv4 address. Systems cannot use simple IP address banning to fight fraud without blocking entire geographic cohorts of legitimate buyers.
- **Cash-on-Delivery (COD) Dynamics:** Over 95% of transactions are paid in cash at the customer's doorstep. Returned parcels take between 4 and 14 days to travel back through courier networks to the warehouse in Tébessa. Couriers withhold transit fees, collection commissions, and return charges directly from bank payout settlements.

---

## 2. Complete Technology Stack & Architectural Roles

### 2.1 Next.js 16 (React 19.2 & App Router)
- **Role:** Primary full-stack web application framework.
- **Server Components:** Delivers zero-JavaScript server-rendered HTML for catalog browsing, keeping the initial payload lightweight for mobile networks.
- **Server Actions:** Manages all data mutations (checkout, order updates, stock adjustments) with server-side validation.
- **Route Handlers:** Handles incoming webhooks from logistics partners (`/api/webhooks/*`) and edge autocomplete search endpoints.
- **Proxy Script (`proxy.ts`):** Replaces legacy middleware to handle routing, device detection, and header normalization cleanly at the edge.

### 2.2 Neon PostgreSQL (Serverless)
- **Role:** Primary relational data store and ACID transaction engine.
- **Data Integrity:** Provides row-level locking (`SELECT ... FOR UPDATE`), strict relational foreign keys, integer currency math, and database branches for developer staging.
- **Connection Optimization:** Configured with Neon's PgBouncer transaction-mode pooler endpoint to multiplex serverless connections without hitches during traffic spikes.

### 2.3 Drizzle ORM Dual-Driver Architecture
- **Stateless HTTP Driver (`dbHttp` via `neon-http`):** Executes single-shot read queries in parallel using stateless HTTPS requests. Consumes zero persistent connection pool slots. Used for high-traffic public catalog feeds, product pages, and read-only admin lists.
- **Transaction Pool Driver (`dbTx` via `neon-serverless` Pool):** Configured with a warm connection pool (`max: 5`, `idleTimeoutMillis: 5000`) pointed at the Neon transaction pooler. Manages multi-statement ACID transactions (`BEGIN ... COMMIT`) for checkout reservations, POS sales, customs recalculations, and courier dispatches.

### 2.4 Cloudflare R2 & Image Optimization (`sharp`)
- **Role:** High-performance object storage for media and product assets.
- **Workflow:** When staff upload product photos in the admin panel, the server converts them directly into modern WebP format using `sharp` before uploading them to Cloudflare R2.
- **Benefit:** Zero egress bandwidth costs, faster mobile loading, and elimination of serverless ephemeral filesystem crashes.

### 2.5 Upstash Redis
- **Role:** Ultra-low latency memory cache and distributed coordinator.
- **Capabilities:** Executes sliding-window rate limiting in under 5 milliseconds, coordinates lock leases, and holds short-lived single-use handoff tokens for seamless transitions between in-app WebViews and native mobile browsers.

### 2.6 Better-Auth
- **Role:** Authentication, session management, and role-based access control.
- **Architecture:** Backed by persistent PostgreSQL session tables, allowing instantaneous server-side session revocation when administrators ban fraudulent accounts. Supports step-up password re-entry for high-risk financial and inventory modifications.

### 2.7 Tailwind CSS v4 & RTL Support
- **Role:** Zero-runtime utility styling.
- **Localization:** Uses native CSS logical properties (`margin-inline-start`, `padding-inline-end`) to provide flawless right-to-left (RTL) Arabic layout rendering across storefronts and high-density ERP data tables.

---

## 3. Core Database Architecture & State Models

### 3.1 Five-Bucket Inventory Model (`product_variants`)
Physical stock is tracked across five mutually exclusive integer columns to prevent inventory leaks and handle courier transit delays:
1. **Available Stock (`stock_available`):** Units sitting on warehouse shelves in Tébessa ready for immediate sale.
2. **Reserved Stock (`stock_reserved`):** Units allocated to active, unshipped online orders (pending phone confirmation, confirmed, or currently being packed).
3. **Shipped Stock (`stock_shipped`):** Units physically dispatched and currently on the road with national couriers or local delivery drivers. Units stay in this bucket until delivered or physically received back at the warehouse dock.
4. **Quarantine Stock (`stock_quarantine`):** Units returned from delivery that have been physically scanned at the warehouse dock and are awaiting inspection, as well as damaged goods.
5. **B-Stock (`stock_b`):** Units inspected and found to have cosmetic flaws or minor defects, offered at special discounts in a dedicated, isolated section of the store.

### 3.2 Orders and Line Items (`orders`, `order_items`)
- **Optimistic Versioning:** Every order has an integer `version` column that increments on every update to prevent simultaneous edits between customers and call center staff.
- **Call-Lock Lease:** Tracks `editing_roller_id` and `editing_locked_until` (a 3-minute soft lease) so customer self-edits are paused while an agent confirms details over the phone.
- **Pack Isolation:** In `order_items`, components belonging to a bundle pack include a `pack_instance_id` and are never merged with standalone items of the same SKU.
- **Exact Remainder-Safe Math:** When refunding or returning partial quantities of a line item, the system calculates exact integer DZD refunds using division rounding down, sweeping the exact accumulated remainder on the final unit so total refunds match line totals to the exact dinar.

### 3.3 Multi-Parcel Logistics Schema (`shipments`, `courier_settlements`)
- **Multi-Colis (`shipments` 1:N with `orders`):** When bulky bicycle items (such as a frame and a wheelset) cannot fit in a single box, the order splits into multiple numbered shipment records, each with its own tracking number. An order is only fully delivered when all child parcels reach terminal delivery.
- **Courier Batch Settlement (`courier_settlements`):** When couriers remit collected cash via bank transfer, this ledger voucher reconciles the gross COD collected, subtracts the courier's base shipping tariffs, accounts for the 1% to 1.5% COD collection tax, registers hub overweight adjustments, and deducts return fees, clearing courier receivables to zero.

### 3.4 Virtual Employee Wallets (`agent_virtual_wallets`)
- **Purpose:** In Algeria, customers often pay order deposits via phone airtime transfers (Flexy) sent to an agent's personal phone.
- **Mechanics:** Flexy deposits do not enter the physical cash drawer. They are credited to the agent's virtual sub-ledger as a personal debt owed to the company.
- **Payroll Offsetting:** At the end of each month, the total balance in the agent's virtual wallet is deducted directly from their calculated base salary and commissions.

### 3.5 Immutable Accounting and Audit Ledgers
- Tables including `stock_ledger`, `financial_ledger`, `audit_logs`, and `zakat_snapshots` are strictly append-only.
- Direct database row updates (`UPDATE`) and deletions (`DELETE`) are prohibited. Any financial or inventory adjustment requires a linked compensating entry.
- The stock ledger enforces uniqueness on order ID, event type, and idempotency reference to prevent duplicate processing.

---

## 4. Concurrency Protection & Global Lock Hierarchy

To prevent database deadlocks (`40P01`) under heavy concurrent traffic, all database transactions touching multiple tables follow a strict, unvarying lock order:

**1. Orders (Ascending ID)  ->  2. Product Variants (Ascending ID)  ->  3. Coupons and Discounts (Ascending ID)**

### 4.1 Checkout Order Creation
- The transaction locks the requested `product_variants` in ascending order (`FOR UPDATE`), checks stock availability, decrements available stock, increments reserved stock, inserts the order and line items, and updates the coupon usage count as the very last step immediately before committing.
- Holding the coupon lock for less than 1 millisecond prevents flash-sale bottlenecks.

### 4.2 Showroom Point-of-Sale (POS) Stock Override
- When a walk-in retail customer purchases an item in the Tébessa showroom that is currently reserved by an unconfirmed online order:
  1. The system identifies eligible unconfirmed online orders.
  2. It locks the victim online order first (`ORDER BY id ASC FOR UPDATE SKIP LOCKED`).
  3. It locks the product variant second (`ORDER BY id ASC FOR UPDATE`).
  4. It transitions the victim online order to an explicit status (`ON_HOLD_STOCK_SHORTAGE`), deducts the reserved inventory, and registers the retail sale.
  5. Negative stock counts and fulfillment errors are completely prevented.

### 4.3 Retroactive Customs Cost Replay (`replayRetroactivePMP`)
- When late customs fees arrive for an already-received import invoice, the system locks all affected in-flight orders first (`PACKED` and `SHIPPED`), locks the affected product variants second, and recalculates the weighted average cost across historical ledger entries in a single set-based SQL transaction.

---

## 5. End-to-End Operational Workflows

### 5.1 Storefront Browsing, Cart Handoff, and Checkout

#### In-App WebView Cart Persistence
- Shoppers browsing inside Instagram, Facebook, or TikTok have their shopping carts stored simultaneously in local browser storage and secure HTTP cookies.
- As the cart changes, the system updates the URL query string with a stateless, tamper-proof HMAC-signed token containing variant IDs and quantities.
- If the customer uses the native app menu to "Open in Chrome" or "Open in Safari", the target browser reads the token from the URL, restores the exact cart items, and immediately removes the token from the address bar. The cart is preserved across isolated mobile app sandboxes.

#### Phase 1: Frictionless Order Placement (Zero Auth Barrier)
- Shoppers enter only their full name, 10-digit mobile phone number, delivery address, Wilaya, and Commune.
- Phone numbers are scrubbed of international prefixes (`00213` or `+213`) and standardized into a 10-digit format starting with `05`, `06`, or `07`.
- The system checks three independent rate-limiting buckets in Upstash Redis (phone limit, device fingerprint limit, and regional CGNAT subnet limit).
- Legitimate orders immediately reserve stock and enter the confirmation queue with an `UNVERIFIED_GUEST` badge. Suspicious orders are placed on security hold without reserving inventory, preventing malicious bots from exhausting available stock.

#### Phase 2: Post-Order Account Upgrade
- Once the order is confirmed, the thank-you page allows customers to set an optional password or connect a Google account.
- If browsing inside a restricted social WebView where Google blocks login popups, the customer can create a password directly or click an external handoff button that launches their native mobile browser with a secure, 5-minute single-use token to complete Google linking.
- If an existing registered customer places a guest order with their regular phone number, account linking is held until verified to prevent account takeover.

### 5.2 Call Center (Roller) Operations & Warehouse Packaging

#### Call Center Confirmation Queue
- Orders appear in an agent dashboard with one-click dialer links and quick status toggles.
- Opening an order locks it with a 3-minute renewable lease, preventing customer self-edits while the agent is talking on the phone.
- The customer's order tracking page polls every 10 seconds and automatically shows changes made by the agent without requiring a manual browser refresh.

#### Local Tébessa Delivery Delegation
- For orders delivered within the Wilaya of Tébessa, checkout displays an estimated price range (such as 150 DZD to 300 DZD).
- The local driver contacts the customer, agrees on the drop-off location, and inputs the final negotiated fee within the configured range.
- The system prevents the driver from saving amounts outside the minimum and maximum boundaries and cleanly separates the delivery fee split upon final settlement.

#### Bulky Item Volumetric Packaging
- Bicycle parts with high volume (frames, wheelsets, rims) are tagged as requiring dedicated boxes.
- Small accessories (cables, lubricant, pedals) are nested inside the free cavity space of the frame box up to the courier's maximum weight limit.
- If total bulk exceeds parcel volume limits, the order automatically generates multiple shipping labels.

### 5.3 Resilient Courier Integration (Yalidine, ZR Express, Ecotrack)

#### Three-Phase Idempotent Dispatch
To ensure identical orders are never assigned duplicate shipping labels:
1. **Phase 1 (Lease):** The warehouse system claims a 60-second atomic lease on the order record in the database. Any duplicate clicks or concurrent requests are rejected immediately.
2. **Phase 2 (External Call):** The server makes the external HTTP request to the courier's API. If a network timeout occurs, the system queries the courier using the merchant order ID before attempting a retry.
3. **Phase 3 (Commit):** The tracking code is saved, units move from reserved stock to shipped stock, unit costs are snapshotted, and the order status updates to shipped.

#### Webhook Synchronization & Return Lag
- Incoming courier status webhooks are authenticated with cryptographic HMAC signatures.
- Out-of-order status notifications (such as an in-transit update arriving after a delivery update) are rejected by a strict one-way state machine.
- When a parcel is flagged as returned (`RETOUR`), the status updates to returning in transit, but the physical units remain in the shipped stock bucket until the parcel arrives at the Tébessa warehouse dock and is physically scanned by warehouse staff.

---

## 6. Financial Architecture & SCF Compliance

### 6.1 Weighted Average Cost (PMP / CUMP)
- For local purchases, shipping costs are distributed across line items to determine the true landed cost per piece.
- For international imports (e.g. containers from China), purchase payments deduct cash immediately while goods are marked as in transit. Upon arrival, customs clearance fees, port handling, and international freight are allocated across products proportionally to item value.
- The weighted average unit cost (`NUMERIC(14,4)`) is recalculated dynamically without floating-point rounding errors.

### 6.2 Flexy Virtual Wallet Reconciliation
- **Successful Delivery:** Full revenue is recognized; the courier remits cash minus the deposit, and the deposit portion is recognized from the employee's virtual wallet.
- **Customer Refusal (Customer Fault):** The deposit is converted to revenue, the return shipping fee is paid from cash, and the net surplus is credited to operational profit.
- **Company Error Return:** The deposit is refunded to the customer from the cash drawer, the return fee is recorded as an operational loss, and the debt remains on the employee's wallet.
- **Agent Error Return:** Return shipping costs are charged directly as a penalty debit against the responsible agent's virtual wallet, offsetting their monthly pay.
- **Late Compensation:** If a customer later reimburses a lost return, the order converts to a compensated return, reversing the loss entry and recording the net profit.

---

## 7. Real-Time Zakat Hawl Engine

### 7.1 Real-Time Zakat Base Calculation
The platform continuously maintains a real-time Zakat balance for commercial goods (Urud al-Tijarah). The calculation strictly follows Shariah guidelines and Algerian accounting standards:

$$\begin{aligned}
\text{Zakat Base} = &\phantom{+} \text{Current Selling Value of Available Stock} \\
&+ \text{Current Selling Value of Reserved Stock} \\
&+ \text{Current Selling Value of Active Outbound Shipped Stock} \\
&+ \text{Cost Value (PMP) of Quarantine Stock} \\
&+ \text{Cost Value (PMP) of Returning In-Transit Stock} \\
&+ \text{Discounted Selling Value of B-Stock} \\
&+ \text{Purchase Cost of In-Transit Imports} \\
&+ \text{Physical Cash Available in Drawer} \\
&+ \text{Net Courier Receivables from Delivered Parcels} \\
&+ \text{Net Local Delivery Driver Receivables} \\
&+ \text{Total Balances in Agent Virtual Wallets} \\
&- \text{Unpaid Supplier Invoices} \\
&- \text{Accrued Courier Fees and Return Liabilities} \\
&- \text{Accrued Employee Payroll and Commissions} \\
&- \text{Customer Deposits Held on Unshipped Orders}
\end{aligned}$$

### 7.2 Annual Hawl Closure
- When the annual lunar Hawl completes and net assets exceed the legal minimum threshold (Nissab), the Super Admin triggers the Hawl closure action.
- The database writes an immutable, non-editable snapshot containing the exact detailed breakdown of all asset and liability categories.
- The 2.5% Zakat payment is recorded as a capital distribution from equity (`ZAKAT_DISTRIBUTION`) rather than an operational operating expense, ensuring operational profit calculations between business partners remain completely accurate.

---

## 8. Security, Permissions, and Anti-Fraud Matrix

### 8.1 Role-Based Access Control (RBAC) Data Isolation
- **Storefront & Public Clients:** Server-side DTO mappers and Drizzle column projections physically exclude purchase costs (`unit_cost_pmp`), supplier identities, and staff notes. These fields are never fetched into server component memory for public routes, making it impossible for margins to leak into browser inspection tools.
- **Call Center Agents (Rollers):** Interface displays customer contact info, delivery fields, and retail totals. Profit margins and wholesale costs are completely hidden.
- **Warehouse Managers:** Displays product details, storage locations, quantities, and internal handling notes, but hides profit metrics.
- **Super Administrators:** Full access to financial ledgers, net profit calculations, partner splits, and Zakat tools.

### 8.2 Three-Tier Anti-Fraud Defense
1. **Tier 1 (Phone Rate Limits):** Upstash Redis restricts a single normalized phone number to a maximum of 2 unconfirmed orders per 24 hours.
2. **Tier 2 (Device Fingerprint):** Restricts unique browser instances to 3 orders per hour.
3. **Tier 3 (CGNAT Regional Subnet Velocity):** Monitors order frequency across shared carrier `/24` IP blocks. High traffic triggers adaptive verification challenges or routes orders to manual security review rather than imposing blanket IP bans that would lock out other mobile users.

### 8.3 Safe Administrative Reversions
- Soft-deletion applies strictly to visual catalog items (moving products or categories to a trash bin).
- Any reversal of inventory quantities or financial records requires administrator password re-verification (`Admin Override Lock`).
- Reversals are recorded as linked compensating entries in the immutable ledgers. History is never overwritten or deleted.
