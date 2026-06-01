# PluginAny Frontend Security Update

## What We Did (Backend — DONE ✅)

- Locked raw tables (`stations`, `station_reviews`, `charger_units`) from anon access
- Created safe views (`stations_public_view`, `reviews_public_view`) that hide PII
- Views use `security_invoker` so they respect RLS
- Writes are blocked for anon users

## What You Need To Do (Frontend)

### Step 1: Search & Replace in your codebase

Open your PluginAny frontend project and do a **find-and-replace**:

| Find | Replace With |
|---|---|
| `.from('stations')` | `.from('stations_public_view')` |
| `.from("stations")` | `.from("stations_public_view")` |

> [!CAUTION]
> **Do NOT replace** any `.insert(`, `.update(`, `.delete(` calls on `stations`.
> Those are admin operations using the `authenticated` role and must stay on the raw table.
> **Only replace SELECT queries** (`.select(`, `.eq(`, `.order(`, etc.)

### Step 2: Reviews — same thing

| Find | Replace With |
|---|---|
| `.from('station_reviews').select` | `.from('reviews_public_view').select` |
| `.from("station_reviews").select` | `.from("reviews_public_view").select` |

> [!CAUTION]
> Keep `.from('station_reviews').insert(...)` as-is — logged-in users need to write reviews to the raw table.

### Step 3: Charger Units

You need to first create a view in **SQL Editor**:

```sql
CREATE VIEW public.charger_units_public_view
WITH (security_invoker = true) AS
SELECT id, station_id, charger_type, connector_type,
       power_kw, status, is_deleted
FROM charger_units
WHERE is_deleted = false;

GRANT SELECT ON public.charger_units_public_view TO anon;
```

Then in your frontend:

| Find | Replace With |
|---|---|
| `.from('charger_units').select` | `.from('charger_units_public_view').select` |

### Step 4: Test your app

After making the changes:

1. Open your app in the browser
2. Check that the **station map loads** (stations show up)
3. Check that **station detail pages** show reviews and charger info
4. Check that **logged-in admins can still add/edit stations**
5. Check that **users can still submit reviews**

### Summary of what's public vs locked

| Data | Anon (public) | Authenticated (logged in) |
|---|---|---|
| Station list (no PII) | ✅ via `stations_public_view` | ✅ via raw table |
| Station host_email/phone | 🔒 Hidden | ✅ Visible |
| Reviews (no user email) | ✅ via `reviews_public_view` | ✅ via raw table |
| Charger units | ✅ via `charger_units_public_view` | ✅ via raw table |
| User profiles | 🔒 Blocked | ✅ Own profile only |
| Marketplace items | ✅ Public | ✅ Public |
| All writes (insert/update/delete) | 🔒 Blocked | ✅ Allowed |
