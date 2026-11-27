import type { WorkflowFileEntry } from '#shared/types/workflow-files'
import { DEFAULT_WORKFLOW_DIR, WORKFLOW_FILE_EXTENSION } from '#shared/types/workflow-files'
import { parentDirectory } from '#shared/utils/posix-paths'
import { useFlowStore } from '~/stores/flow'

const NAME_RE = /^[^<>:"/\\|?*]+$/
const FOLDER_RE = /^[^<>:"\\|?*]*$/
const JSON_EXTENSION_RE = /\.json$/i
const TIMESTAMP_SEPARATOR_RE = /[:T]/g
const EDGE_SLASH_RE = /^\/+|\/+$/g

function hasControlCharacters(value: string): boolean {
  for (const char of value) {
    if (char.charCodeAt(0) < 32)
      return true
  }
  return false
}

/**
 * State and validation for the "save workflow" form: where the file goes and
 * whether that target is allowed. Kept out of the component so the dialog only
 * renders.
 */
export function useWorkflowSaveForm() {
  const store = useFlowStore()
  const { t } = useI18n()

  const name = ref('')
  const folder = ref(DEFAULT_WORKFLOW_DIR)
  const overwrite = ref(false)
  const selectedExistingPath = ref('')
  const error = ref('')

  const normalizedName = computed(() => name.value.trim().replace(JSON_EXTENSION_RE, ''))

  const folderIsSafe = computed(() => {
    const value = folder.value.trim()
    if (!value)
      return true
    if (hasControlCharacters(value) || !FOLDER_RE.test(value))
      return false
    return !value.split('/').includes('..')
  })

  const nameError = computed(() => {
    const value = normalizedName.value
    if (!value)
      return t('workflowFiles.nameRequired')
    if (hasControlCharacters(value) || !NAME_RE.test(value) || value === '.' || value === '..')
      return t('workflowFiles.invalidName')
    return ''
  })

  const targetPath = computed(() => {
    const value = normalizedName.value
    if (!value)
      return ''
    const directory = folder.value.trim().replace(EDGE_SLASH_RE, '')
    return `${directory ? `${directory}/` : ''}${value}${WORKFLOW_FILE_EXTENSION}`
  })

  function defaultName(): string {
    if (store.activeWorkflowPath) {
      const base = store.activeWorkflowPath.split('/').pop() ?? ''
      return base.replace(JSON_EXTENSION_RE, '')
    }
    const stamp = new Date().toISOString().slice(0, 16).replace(TIMESTAMP_SEPARATOR_RE, '-')
    return `workflow-${stamp}`
  }

  function defaultFolder(): string {
    return store.activeWorkflowPath
      ? parentDirectory(store.activeWorkflowPath) ?? ''
      : DEFAULT_WORKFLOW_DIR
  }

  /** Reset to the folder and name of the workflow that is currently open. */
  function reset() {
    name.value = defaultName()
    folder.value = defaultFolder()
    overwrite.value = false
    selectedExistingPath.value = ''
    error.value = ''
  }

  function selectExistingFile(entry: WorkflowFileEntry) {
    selectedExistingPath.value = entry.path
    folder.value = parentDirectory(entry.path) ?? ''
    name.value = entry.name.replace(JSON_EXTENSION_RE, '')
    error.value = ''
    overwrite.value = true
  }

  function applyFolder(path: string) {
    folder.value = path
  }

  /** The server refused because the file exists: turn the next click into an overwrite. */
  function markConflict() {
    overwrite.value = true
    selectedExistingPath.value = targetPath.value
  }

  watch([name, folder], () => {
    error.value = ''
    if (targetPath.value !== selectedExistingPath.value) {
      selectedExistingPath.value = ''
      overwrite.value = false
    }
  })

  return {
    name,
    folder,
    overwrite,
    selectedExistingPath,
    error,
    normalizedName,
    folderIsSafe,
    nameError,
    targetPath,
    reset,
    selectExistingFile,
    applyFolder,
    markConflict,
  }
}
