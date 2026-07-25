# Iterative Partner Examples

## Shared demo

`examples/ad-runner-template.xlsx` contains `shared-demo`, where `animeplex.lol` repeats across rows for Alejandro and Partner B. Both have 50% Share Targets, two simulated external network accounts, and a partner-owned house unit.

Expected route:

```text
Select Alejandro
  -> ExoClick account A no-fill
  -> Adsterra account A filled
  -> Fill Credit Alejandro
```

Open Yield route:

```text
Select Partner B
  -> all Partner B external steps fail
  -> Recovery Pass
  -> Alejandro fills
  -> Fill Credit Alejandro
  -> Partner B accumulates Share Debt
```

## Solo demo

`solo-demo` uses `solo.example` with one operator and several Network Steps. It demonstrates the same Partner Lane iteration as a multi-network fallback router.
