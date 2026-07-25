# Iterative Partner Model

The Iterative Partner Model treats every advertisement opportunity as something that can be routed fairly among several revenue participants. Ad Runner first selects the partner whose share is due. It then iterates through that partner’s available networks until one fills. If the route fails, Ad Runner follows an explicit recovery policy. This allows shared websites and solo multi-network operations to use the same simple engine.

## Product principle

One slot can serve many partners. Each partner can have many networks. Ad Runner iterates fairly until the opportunity is filled.

## Partner Selection

```text
Opportunity Cycle
  -> read Share Ledger
  -> normalize Share Targets
  -> compute Share Debt
  -> select Partner with the largest debt
```

## Partner Lane Iteration

```text
Selected Partner Lane
  -> Network Step 1
  -> Network Step 2
  -> partner house unit
  -> stop on first confirmed fill
```

## Protected Share

```text
Selected partner lane fails
  -> selected partner house unit
  -> Neutral Fallback
  -> collapse slot
```

Protected Share does not transfer the opportunity to another partner.

## Open Yield Recovery Pass

```text
Selected partner lane fails
  -> Recovery Pass through another eligible Partner Lane
  -> Neutral Fallback
  -> collapse slot
```

If another partner fills during the Recovery Pass, Fill Credit goes to the final partner and the original selected partner keeps Share Debt.

## Fill Credit

```text
script loaded != Fill Credit
confirmed rendered impression -> Fill Credit
neutral fallback -> no partner credit by default
```

## Share Debt Compensation

```text
Share Debt = Share Target - Actual Fill Share
```

A partner behind target receives priority in future Opportunity Cycles.

## Direct Credit Routing

```text
Partner A account -> network pays Partner A
Partner B account -> network pays Partner B
Ad Runner routes opportunities; it does not settle money.
```

Ad Runner does not combine partner credentials, rewrite publisher IDs, expose private credentials, calculate legal ownership, or promise exact monetary equality. Actual earnings can differ because CPM, CPC, advertiser demand, geography, reporting, clicks, and network deductions differ.

## Two-person example

Alejandro and Partner B each receive a 50% Share Target for `animeplex.lol` / `right_rail`. If Alejandro is behind confirmed fills, Ad Runner selects Alejandro, tries ExoClick account A, then Adsterra account A, then Alejandro’s house unit. If Adsterra fills, Alejandro receives Fill Credit.

## Solo-operator example

A solo operator can model each internal account or network route as a partner or use one partner with many Network Steps. The same engine tries external networks first and uses a house unit only after paid routes fail.
