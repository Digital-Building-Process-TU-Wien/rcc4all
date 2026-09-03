import type { FilterRow, FilterRowKey, FilterRowMode, FilterRowOperator, FilterRows } from '../types'

interface CsvColumn {
  key: FilterRowKey
  label: string
}

export const CSV_COLUMNS: Array<CsvColumn> = [
  { key: 'mode', label: 'mode' },
  { key: 'entity_type', label: 'entity_type' },
  { key: 'predefined_type', label: 'predefined_type' },
  { key: 'property_set', label: 'property_set' },
  { key: 'property_name', label: 'property_name' },
  { key: 'operator', label: 'operator' },
  { key: 'value', label: 'value' },
]

const OPERATORS: FilterRowOperator[] = [
  '==',
  '!=',
  '<',
  '>',
  '<=',
  '>=',
  'contains',
  'starts_with',
  'ends_with',
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

function rowFromCsvRecord(record: Record<string, string>): FilterRow {
  const mode = record.mode ?? ''
  const operator = record.operator ?? ''

  return {
    mode: ['include', 'exclude', 'disabled'].includes(mode) ? mode as FilterRowMode : 'include',
    entity_type: record.entity_type ?? '',
    predefined_type: record.predefined_type ?? '',
    property_set: record.property_set ?? '',
    property_name: record.property_name ?? '',
    operator: OPERATORS.includes(operator as FilterRowOperator) ? operator as FilterRowOperator : '==',
    value: record.value ?? '',
  }
}

export function rowsFromCsv(text: string): FilterRows {
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
  }) as FilterRows
}

export function exportFilterRowsToCsv(filterRows: FilterRows, filename: string = 'ifc-element-filter.csv'): void {
  const header = CSV_COLUMNS.map(column => column.label).join(';')
  const body = filterRows.map(row => CSV_COLUMNS
    .map(column => escapeCsvValue(row[column.key] ?? ''))
    .join(';'))
  const csv = `\uFEFF${['sep=;', header, ...body].join('\r\n')}\r\n`
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export async function importFilterRowsFromCsv(file: File): Promise<FilterRows> {
  const text = await file.text()
  return rowsFromCsv(text)
}
