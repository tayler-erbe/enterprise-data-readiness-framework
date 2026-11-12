# Owner work lists

Ranked by priority (usage x gap).
Nothing here changes a score until the owner confirms it.

## Accounts Payable

1 table(s) below target.

### `FIN.SUPPLIER_INVOICE`: level 1 Described, target 4, priority 7800

- To reach level 2: Grain not stated. Say what one row is.
- Can't tell yet: 4 index(es) exist but no key or join is named.
- Can't tell yet: No column metadata in this export, so column coverage can't be checked.
- Can't tell yet: No column metadata in this export, so coded columns can't be checked.
- Later, for level 3: Rules in prose, not in fields: known defect: "May contain invalid invoice dates such as 01/01/200."
- Note: No row count.

## Benefits Office

1 table(s) below target.

### `HR.BENEFIT_PLAN_HIST`: level 1 Described, target 4, priority 1230

- Privacy tier: C, suggested from the name; confirm with the steward
- To reach level 2: Grain not stated. Say what one row is.
- Can't tell yet: 2 index(es) exist but no key or join is named.
- Can't tell yet: No column metadata in this export, so column coverage can't be checked.
- Can't tell yet: No column metadata in this export, so coded columns can't be checked.
- Note: Link uses http://; likely an old address.
- Note: No row count.

## Contract Accounting

1 table(s) below target.

### `FIN.CONTRACT`: level 3 Governed, target 4, priority 3100

- Privacy tier: B
- To reach level 4: Not in the semantic layer.
- To reach level 4: 0 verified question(s); need 5.

## General Accounting

1 table(s) below target.

### `FIN.LEDGER_ENTRY`: level 1 Described, target 4, priority 15300

- To reach level 2: Grain not stated. Say what one row is.
- Can't tell yet: 2 index(es) exist but no key or join is named.
- Can't tell yet: No column metadata in this export, so column coverage can't be checked.
- Can't tell yet: No column metadata in this export, so coded columns can't be checked.
- Later, for level 3: Rules in prose, not in fields: validity window: "Some entries dated before March 2015 are known to be wrong."
- Note: No row count.

## HR Records

1 table(s) below target.

### `HR.EMP_ADDRESS_HIST`: level 2 Usable, target 4, priority 1400

- To reach level 3: Rules in prose, not in fields: validity window: "The old region field was retired with the 2019 payroll change;"
- Note: No row count.
- Note: Draft grain from the key, to confirm: one row per EMP_ID, EFF_DT.

## No owner on record

16 table(s) below target.

### `SALES.ORDER_LINE`: level 1 Described, target 4, priority 27300

- To reach level 2: Grain not stated. Say what one row is.
- Can't tell yet: 4 index(es) exist but no key or join is named.
- Can't tell yet: No column metadata in this export, so column coverage can't be checked.
- Can't tell yet: No column metadata in this export, so coded columns can't be checked.
- Note: Short description (3 words).
- Note: No row count.

### `SALES.CUST_PERIOD`: level 1 Described, target 4, priority 26400

- To reach level 2: 2 of 6 columns described (33%; need 80%).
- To reach level 2: 2 of 3 coded columns have no lookup: SEG_CD, RGN_CD
- Note: No row count.
- Note: Draft grain from the key, to confirm: one row per CUST_ID, PERIOD_CD.

### `SALES.PRODUCT_LISTING`: level 1 Described, target 4, priority 15900

- To reach level 2: Grain not stated. Say what one row is.
- Can't tell yet: 3 index(es) exist but no key or join is named.
- Can't tell yet: No column metadata in this export, so column coverage can't be checked.
- Can't tell yet: No column metadata in this export, so coded columns can't be checked.
- Note: No row count.

### `REF.PERIOD_CD`: level 1 Described, target 3, priority 14800

- Privacy tier: A
- To reach level 2: Grain not stated. Say what one row is.
- Can't tell yet: 1 index(es) exist but no key or join is named.
- Can't tell yet: No column metadata in this export, so column coverage can't be checked.
- Can't tell yet: No column metadata in this export, so coded columns can't be checked.
- Note: Short description (2 words).
- Note: No row count.

### `HR.POSITION`: level 2 Usable, target 4, priority 3600

- Privacy tier: B
- To reach level 3: No named owner or steward.
- To reach level 3: No trust level recorded (for example: system of record, self-reported).
- Note: Draft grain from the key, to confirm: one row per POSITION_NO, FISCAL_YR.

### `FIN.QUOTE_ORDER_FACT`: level 1 Described, target 4, priority 2700

- Can't tell yet: 1 index(es) exist but no key or join is named.
- Can't tell yet: No column metadata in this export, so column coverage can't be checked.
- Can't tell yet: No column metadata in this export, so coded columns can't be checked.
- Note: No row count.

### `FIN.QUOTE_ORDER_LINE_FACT`: level 0 Undocumented, target 4, priority 1400

- To reach level 1: No table description.
- To reach level 1: Nothing to read.
- Note: No row count.

### `HR.EMP_CERT_HIST`: level 1 Described, target 4, priority 780

- To reach level 2: Grain not stated. Say what one row is.
- Can't tell yet: 1 index(es) exist but no key or join is named.
- Can't tell yet: No column metadata in this export, so column coverage can't be checked.
- Can't tell yet: No column metadata in this export, so coded columns can't be checked.
- Later, for level 3: Rules in prose, not in fields: trust level: "Self-reported and never checked."
- Note: No row count.

### `SALES.CREDIT_APPL_PART_1`: level 1 Described, target 4, priority 660

- Privacy tier: C, suggested from the name; confirm with the steward
- To reach level 2: Grain not stated. Say what one row is.
- Can't tell yet: 1 index(es) exist but no key or join is named.
- Can't tell yet: No column metadata in this export, so column coverage can't be checked.
- Can't tell yet: No column metadata in this export, so coded columns can't be checked.
- Note: Short description (5 words).
- Note: No row count.

### `FIN.CARD_ALLOC`: level 1 Described, target 4, priority 360

- To reach level 2: Grain not stated. Say what one row is.
- Can't tell yet: 1 index(es) exist but no key or join is named.
- Can't tell yet: No column metadata in this export, so column coverage can't be checked.
- Can't tell yet: No column metadata in this export, so coded columns can't be checked.
- Note: Short description (6 words).
- Note: No row count.

### `HR.EMP_SKILL_HIST`: level 1 Described, target 4, priority 270

- To reach level 2: Grain not stated. Say what one row is.
- Can't tell yet: 1 index(es) exist but no key or join is named.
- Can't tell yet: No column metadata in this export, so column coverage can't be checked.
- Can't tell yet: No column metadata in this export, so coded columns can't be checked.
- Later, for level 3: Rules in prose, not in fields: trust level: "Skills listed by employees in their â€œprofileâ€, self-reported.Â"
- Note: No row count.
- Note: Encoding damage in description (for example Â or â€œ). Re-save as UTF-8.

### `FIN.INVOICE_HDR`: level 0 Undocumented, target 4, priority 160

- To reach level 1: Description is a placeholder: 'INVOICE_HDR'.
- Note: No row count.

### `HR.EMP_HEALTH_COND_HIST`: level 1 Described, target 4, priority 90

- Privacy tier: C, suggested from the name; confirm with the steward
- To reach level 2: Grain not stated. Say what one row is.
- Can't tell yet: 1 index(es) exist but no key or join is named.
- Can't tell yet: No column metadata in this export, so column coverage can't be checked.
- Can't tell yet: No column metadata in this export, so coded columns can't be checked.
- Note: Short description (2 words).
- Note: No row count.

### `HR.EMP_HR_NOTE`: level 0 Undocumented, target 4, priority 40

- Privacy tier: C, suggested from the name; confirm with the steward
- To reach level 1: No table description.
- To reach level 1: Nothing to read.
- Note: No row count.

### `OPS.SCHED_JOB_DETAILS`: level 0 Undocumented, target 4, priority 20

- To reach level 1: No table description.
- To reach level 1: Nothing to read.
- Note: No row count.

### `OPS.POLICY_MAINT`: level 0 Undocumented, target 4, priority 12

- To reach level 1: Description is a placeholder: 'TBD'.
- Note: No row count.
