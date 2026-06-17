# Pending Documentation Updates

This note captures documentation changes that should be applied later to the generated node documentation/schema for `ifc_element_filter`.

## Predefined Type

In the `FilterRow structure` table, extend the `predefined_type` description.

Current text:

```text
Optional PredefinedType enum value. Empty means any predefined type.
```

Add this behavior note:

```text
If the value is not selected from the predefined list but entered manually, the program should treat it as a user-defined type: `PredefinedType == USERDEFINED` and `ObjectType == <entered value>`.
```

## Property Set

In the `FilterRow structure` table, extend the `property_set` description.

Add this behavior note:

```text
If `Attributes` is selected as the property set, it refers to the direct IFC attributes available for the selected entity.
```

## Likely Files To Update Later

- `app/runner/src/openbim_runner/nodes/ifc_element_filter/README.en.md`
- `app/runner/src/openbim_runner/nodes/ifc_element_filter/README.de.md`
- Regenerate web schema afterwards with `npm run generate:schema` from `app/web`.

## Implementation Note

The PredefinedType behavior above is not only documentation if it should affect filtering results. The runner logic must also support the `USERDEFINED` plus `ObjectType` comparison path.
