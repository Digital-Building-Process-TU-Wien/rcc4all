import type { ComparisonRow, Rows } from '../types'
import { CONDITION_LIST, isValidCondition } from '../types'

interface CsvColumn {
  key: keyof ComparisonRow
  label: string
}

export const CSV_COLUMNS: Array<CsvColumn> = [
  { key: 'entity_type', label: 'entity_type' },
  { key: 'property_set', label: 'property_set' },
  { key: 'property_name', label: 'property_name' },
  { key: 'condition', label: 'condition' },
  { key: 'expected_value', label: 'expected_value' },
  { key: 'allowed_values', label: 'allowed_values' },
  { key: 'range_min', label: 'range_min' },
  { key: 'range_max', label: 'range_max' },
  { key: 'inclusive_min', label: 'inclusive_min' },
  { key: 'inclusive_max', label: 'inclusive_max' },
]

const CSV_SPECIAL_CHARS_RE = /[";,\r\n]/
const BOM_RE = /^\uFEFF/
const LINE_BREAK_RE = /\r?\n/

export function escapeCsvValue(value: string | undefined): string {
  const text = value ?? ''

  if (!CSV_SPECIAL_CHARS_RE.test(text))
    return text

  return `"${text.replaceAll('"', '""')}"`
}

function serializeCell(key: keyof ComparisonRow, value: unknown): string {
  if (key === 'allowed_values') {
    if (Array.isArray(value))
      return value.filter(v => typeof v === 'string' && v.trim()).join('|')
    return ''
  }
  if (typeof value === 'boolean')
    return value ? 'true' : 'false'
  return (value as string | undefined) ?? ''
}

export function parseCsv(text: string, delimiter: ',' | ';'): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let value = ''
  let inQuotes = false

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index]
    const nextCharacter = text[index + 1]

    if (character === '"') {
      if (inQuotes && nextCharacter === '"') {
        value += '"'
        index += 1
      }
      else {
        inQuotes = !inQuotes
      }

      continue
    }

    if (character === delimiter && !inQuotes) {
      row.push(value)
      value = ''
      continue
    }

    if ((character === '\n' || character === '\r') && !inQuotes) {
      if (character === '\r' && nextCharacter === '\n')
        index += 1

      row.push(value)
      if (row.some(cell => cell !== ''))
        rows.push(row)

      row = []
      value = ''
      continue
    }

    value += character
  }

  row.push(value)
  if (row.some(cell => cell !== ''))
    rows.push(row)

  return rows
}

function rowFromCsvRecord(record: Record<string, string>): ComparisonRow {
  const inclusive = (value: string | undefined, fallback: boolean): boolean => {
    if (value === undefined || value === '')
      return fallback
    return value.toLowerCase() === 'true' || value === '1'
  }

  const rawCondition = record.condition?.trim() || 'equals'
  if (!isValidCondition(rawCondition)) {
    throw new Error(
      `Invalid condition "${record.condition}" in CSV: expected one of ${CONDITION_LIST}.`,
    )
  }

  return {
    entity_type: record.entity_type ?? '',
    property_set: record.property_set ?? '',
    property_name: record.property_name ?? '',
    condition: rawCondition as ComparisonRow['condition'],
    expected_value: record.expected_value ?? '',
    allowed_values: parseAllowedValues(record.allowed_values),
    range_min: record.range_min ?? '',
    range_max: record.range_max ?? '',
    inclusive_min: inclusive(record.inclusive_min, true),
    inclusive_max: inclusive(record.inclusive_max, true),
  }
}

function parseAllowedValues(raw: string | undefined): string[] {
  const rawValues = (raw ?? '').split('|').map(value => value.trim())
  const values = rawValues.filter(value => value !== '')
  if (values.length === 0 || values.at(-1) !== '')
    values.push('')
  return values
}

export function rowsFromCsv(text: string): Rows {
  const csvText = text.trimStart().replace(BOM_RE, '')
  const firstLine = csvText.split(LINE_BREAK_RE, 1)[0]?.trim().toLowerCase() ?? ''
  const delimiter = firstLine === 'sep=;' || firstLine.includes(';') ? ';' : ','
  const parsedRows = parseCsv(csvText, delimiter)
  if (parsedRows[0]?.[0]?.trim().toLowerCase() === 'sep=;')
    parsedRows.shift()

  if (!parsedRows.length)
    return []

  const header = parsedRows[0]?.map(cell => cell.trim()) ?? []
  const hasHeader = CSV_COLUMNS.every(column => header.includes(column.label))
  const dataRows = hasHeader ? parsedRows.slice(1) : parsedRows
  const columns = hasHeader ? header : CSV_COLUMNS.map(column => column.label)

  return dataRows.map((dataRow) => {
    const record: Record<string, string> = {}

    columns.forEach((column, index) => {
      record[column] = dataRow[index] ?? ''
    })

    return rowFromCsvRecord(record)
  }) as Rows
}

export function exportRowsToCsv(rows: Rows, filename: string = 'loi-check.csv'): void {
  const header = CSV_COLUMNS.map(column => column.label).join(';')
  const body = rows.map((sel) => {
    return CSV_COLUMNS
      .map(column => escapeCsvValue(serializeCell(column.key, sel[column.key])))
      .join(';')
  })
  const csv = `\uFEFF${['sep=;', header, ...body].join('\r\n')}\r\n`
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export async function importRowsFromCsv(file: File): Promise<Rows> {
  const text = await file.text()
  return rowsFromCsv(text)
}
