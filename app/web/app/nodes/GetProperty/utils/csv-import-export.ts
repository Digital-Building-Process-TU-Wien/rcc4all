import type { PropertySelection, Requirements } from '../types'

interface CsvColumn {
  key: keyof PropertySelection
  label: string
}

export const CSV_COLUMNS: Array<CsvColumn> = [
  { key: 'entity_type', label: 'entity_type' },
  { key: 'property_set', label: 'property_set' },
  { key: 'property_name', label: 'property_name' },
]

export function escapeCsvValue(value: string | undefined): string {
  const text = value ?? ''

  if (!/[";,\r\n]/.test(text))
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

function rowFromCsvRecord(record: Record<string, string>): PropertySelection {
  return {
    entity_type: record.entity_type ?? '',
    property_set: record.property_set ?? '',
    property_name: record.property_name ?? '',
  }
}

export function rowsFromCsv(text: string): Requirements {
  const csvText = text.trimStart().replace(/^\uFEFF/, '')
  const firstLine = csvText.split(/\r?\n/, 1)[0]?.trim().toLowerCase() ?? ''
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
  }) as Requirements
}

export function exportRequirementsToCsv(requirements: Requirements, filename: string = 'get-property.csv'): void {
  const header = CSV_COLUMNS.map(column => column.label).join(';')
  const body = requirements.map(sel => CSV_COLUMNS
    .map(column => escapeCsvValue(sel[column.key] ?? ''))
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

export async function importRequirementsFromCsv(file: File): Promise<Requirements> {
  const text = await file.text()
  return rowsFromCsv(text)
}
