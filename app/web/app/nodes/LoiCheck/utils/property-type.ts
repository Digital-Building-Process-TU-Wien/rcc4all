import type { ComparisonRow, IfcAllowedValue, IfcFilterIndex, IfcFilterPropertySet } from '../types'

export interface ResolvedPropertyType {
  dataType: string
  allowedValues: IfcAllowedValue[]
}

export function isBooleanType(type: ResolvedPropertyType): boolean {
  return type.dataType.toLowerCase() === 'boolean'
}

export function isNumericType(type: ResolvedPropertyType): boolean {
  const dataType = type.dataType.toLowerCase()
  return dataType === 'integer' || dataType === 'real'
}

export function hasEnumValues(type: ResolvedPropertyType): boolean {
  return type.allowedValues.length > 0
}

/**
 * Resolve the IFC data type (and allowed enum values) for a comparison row from
 * the loaded IFC 4.3 filter index. Falls back to an empty type (plain textbox)
 * when the entity/pset/property cannot be identified or the resolution is
 * ambiguous (e.g. custom property sets or empty selections).
 */
export function resolvePropertyType(
  index: IfcFilterIndex | undefined,
  row: ComparisonRow,
): ResolvedPropertyType {
  const noType: ResolvedPropertyType = { dataType: '', allowedValues: [] }
  if (!index)
    return noType

  const entities = index.entities ?? []
  const entityType = (row.entity_type ?? '').trim().toUpperCase()
  const propertySet = (row.property_set ?? '').trim()
  const propertyName = (row.property_name ?? '').trim()
  if (!propertyName)
    return noType

  // Candidate property sets: restricted to matching entity, or union across entities.
  let candidatePsets: IfcFilterPropertySet[] = []
  if (entityType) {
    const entity = entities.find(e => e.code.toUpperCase() === entityType)
    if (!entity)
      return noType
    candidatePsets = entity.propertySets
  }
  else {
    candidatePsets = entities.flatMap(e => e.propertySets)
  }

  if (propertySet)
    candidatePsets = candidatePsets.filter(pset => pset.code === propertySet)

  // Collect data types of every matching property across the candidate psets.
  const matches: Array<{ dataType: string, allowedValues: IfcAllowedValue[] }> = []
  for (const pset of candidatePsets) {
    for (const property of pset.properties) {
      if (property.code.toLowerCase() === propertyName.toLowerCase()) {
        matches.push({
          dataType: (property.dataType ?? '').trim(),
          allowedValues: property.allowedValues ?? [],
        })
      }
    }
  }

  if (!matches.length)
    return noType

  // Use the dataType only when all matches agree (avoid ambiguity across psets).
  const distinctTypes = new Set(matches.map(match => match.dataType).filter(Boolean))
  if (distinctTypes.size > 1)
    return noType

  // Only trust allowedValues when every match agrees on the same value set
  // (the previous code could combine a dataType from one match with
  // allowedValues from a different one).
  const allowedSets = new Set(matches.map(match => allowedValuesKey(match.allowedValues)))
  if (allowedSets.size > 1)
    return noType

  const dataType = distinctTypes.size === 1 ? Array.from(distinctTypes)[0]! : ''
  const first = matches[0]!
  return { dataType, allowedValues: first.allowedValues }
}

function allowedValuesKey(allowed: IfcAllowedValue[] | undefined): string {
  return (allowed ?? []).map(value => value.code).join('\u0000')
}
