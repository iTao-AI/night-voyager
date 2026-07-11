# M1 route map

## Primary route

`/demo` is the only M1 product route. It is a synthetic fixture proof of a future product workflow, not a connected domain backend.

```text
/demo
  -> Advisor Ledger
     -> conditional result + Evidence gap
     -> evidence disclosure
     -> required advisor approval
  -> Family Decision Brief (family_review)
     -> linear comparison and confirmation summary
  -> Decision receipt + TimelinePlan (decided)
  -> Malaysia blocked negative path
```

The root `/` remains the M0 bootstrap page. M1 does not introduce authentication, application navigation, mutations, or backend routes.

## Route comprehension contract

Within the first viewport, a reviewer must be able to name:

1. the current lifecycle stage: `advisor_review`;
2. the required human decision: advisor approval after reviewing the Evidence gap;
3. the primary action: `Review evidence`;
4. the boundary: synthetic fixture proof mode.
