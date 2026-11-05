<script setup lang="ts">
import { DEFAULT_WORKFLOW_DIR, DEV_FILES_LABEL } from '#shared/types/workflow-files'
import { parentDirectory } from '#shared/utils/posix-paths'
import WorkflowFileBrowser from '~/components/nodes/WorkflowFileBrowser.vue'
import {
  isWorkflowFileConflict,
  useWorkflowFiles,
  workflowFileErrorMessage,
} from '~/composables/useWorkflowFiles'
import { useWorkflowSaveForm } from '~/composables/useWorkflowSaveForm'
import { useFlowStore } from '~/stores/flow'

const emit = defineEmits<{
  loaded: []
}>()

const store = useFlowStore()
const { hasNodes } = storeToRefs(store)
const { t } = useI18n()
const toast = useToast()
const { loadWorkflow, saveWorkflow } = useWorkflowFiles()

const {
  name: saveName,
  folder: saveDir,
  overwrite,
  selectedExistingPath,
  error: saveError,
  nameError,
  folderIsSafe,
  targetPath,
  reset: resetSaveForm,
  selectExistingFile,
  applyFolder,
  markConflict,
} = useWorkflowSaveForm()

const loadOpen = ref(false)
const loadDir = ref(DEFAULT_WORKFLOW_DIR)
const loadRefreshToken = ref(0)
const selectedPath = ref('')
const loadError = ref('')
const loadingFile = ref(false)

const saveOpen = ref(false)
const saving = ref(false)
const saveRefreshToken = ref(0)
const browseOpen = ref(false)
const browseDir = ref(DEFAULT_WORKFLOW_DIR)

const hasMainModel = computed(() =>
  store.files.some(file => file.slug === 'main' && !!file.path),
)

function activeDirectory(): string {
  return store.activeWorkflowPath
    ? parentDirectory(store.activeWorkflowPath) ?? ''
    : DEFAULT_WORKFLOW_DIR
}

function openLoad() {
  selectedPath.value = ''
  loadError.value = ''
  loadDir.value = activeDirectory()
  loadRefreshToken.value += 1
  loadOpen.value = true
}

function openSave() {
  resetSaveForm()
  saveRefreshToken.value += 1
  saveOpen.value = true
}

function openBrowse() {
  browseDir.value = saveDir.value.trim()
  browseOpen.value = true
}

function chooseFolder() {
  applyFolder(browseDir.value)
  browseOpen.value = false
}

async function confirmLoad() {
  if (!selectedPath.value)
    return

  loadingFile.value = true
  loadError.value = ''
  try {
    const result = await loadWorkflow(selectedPath.value)
    store.hydrate(result.workflow)
    store.setActiveWorkflowPath(result.path)
    loadOpen.value = false
    emit('loaded')
    toast.add({
      title: t('workflowFiles.loaded'),
      description: result.path,
      color: 'success',
    })
  }
  catch (cause) {
    loadError.value = workflowFileErrorMessage(cause, t('workflowFiles.loadFailed'))
  }
  finally {
    loadingFile.value = false
  }
}

async function confirmSave() {
  if (nameError.value) {
    saveError.value = nameError.value
    return
  }
  if (!folderIsSafe.value) {
    saveError.value = t('workflowFiles.invalidFolder')
    return
  }

  saving.value = true
  saveError.value = ''
  try {
    const result = await saveWorkflow({
      path: targetPath.value,
      workflow: store.exportWorkflow(),
      overwrite: overwrite.value,
    })
    store.setActiveWorkflowPath(result.path)
    saveOpen.value = false
    toast.add({
      title: t('workflowFiles.saved'),
      description: result.path,
      color: 'success',
    })
  }
  catch (cause) {
    if (isWorkflowFileConflict(cause)) {
      markConflict()
      saveError.value = t('workflowFiles.conflict', { name: saveName.value.trim() })
    }
    else {
      saveError.value = workflowFileErrorMessage(cause, t('workflowFiles.saveFailed'))
    }
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="flex items-center gap-2">
    <UButton
      color="neutral"
      variant="outline"
      icon="i-lucide-folder-open"
      :label="t('workflowFiles.load')"
      :title="store.activeWorkflowPath ?? t('workflowFiles.load')"
      @click="openLoad"
    />
    <UButton
      color="primary"
      variant="soft"
      icon="i-lucide-save"
      :label="t('workflowFiles.save')"
      :title="store.activeWorkflowPath ?? t('workflowFiles.save')"
      :disabled="!hasNodes"
      @click="openSave"
    />
  </div>

  <UModal
    v-model:open="loadOpen"
    :title="t('workflowFiles.loadTitle')"
    :description="t('workflowFiles.loadDescription')"
  >
    <template #body>
      <div class="space-y-3">
        <UAlert
          v-if="hasNodes"
          color="warning"
          variant="subtle"
          :title="t('workflowFiles.replaceWarning')"
        />
        <WorkflowFileBrowser
          v-model:dir="loadDir"
          mode="files"
          :selected="selectedPath"
          :refresh-token="loadRefreshToken"
          @select="selectedPath = $event.path"
        />
        <UAlert v-if="loadError" color="error" :title="loadError" />
      </div>
    </template>
    <template #footer="{ close }">
      <UButton
        color="neutral"
        variant="outline"
        :label="t('workflowFiles.cancel')"
        @click="close"
      />
      <UButton
        color="primary"
        :label="t('workflowFiles.load')"
        :loading="loadingFile"
        :disabled="!selectedPath"
        @click="confirmLoad"
      />
    </template>
  </UModal>

  <UModal
    v-model:open="saveOpen"
    :title="t('workflowFiles.saveTitle')"
    :description="t('workflowFiles.saveDescription')"
  >
    <template #body>
      <div class="space-y-4">
        <UFormField :label="t('workflowFiles.nameLabel')">
          <UInput
            v-model="saveName"
            :placeholder="t('workflowFiles.namePlaceholder')"
            autofocus
            @keydown.enter="confirmSave"
          />
        </UFormField>

        <UFormField
          :label="t('workflowFiles.folderLabel')"
          :hint="t('workflowFiles.folderHint')"
        >
          <div class="flex gap-2">
            <UInput
              v-model="saveDir"
              :placeholder="DEFAULT_WORKFLOW_DIR"
              class="flex-1"
            />
            <UButton
              color="neutral"
              variant="outline"
              icon="i-lucide-folder-search"
              :label="t('workflowFiles.chooseFolder')"
              @click="openBrowse"
            />
          </div>
        </UFormField>

        <p class="truncate font-mono text-xs text-muted">
          {{ DEV_FILES_LABEL }}/{{ targetPath }}
        </p>

        <UAlert
          v-if="!hasMainModel"
          color="warning"
          variant="subtle"
          :title="t('workflowFiles.noModelWarning')"
        />

        <div class="space-y-2">
          <div>
            <p class="text-sm font-medium text-default">
              {{ t('workflowFiles.existingFiles') }}
            </p>
            <p class="text-xs text-muted">
              {{ t('workflowFiles.existingFilesHint') }}
            </p>
          </div>
          <WorkflowFileBrowser
            v-model:dir="saveDir"
            mode="files"
            :selected="selectedExistingPath"
            :refresh-token="saveRefreshToken"
            @select="selectExistingFile"
          />
        </div>

        <UAlert v-if="saveError" color="error" :title="saveError" />
        <UAlert
          v-else-if="overwrite"
          color="warning"
          variant="subtle"
          :title="t('workflowFiles.overwriteHint')"
        />
      </div>
    </template>
    <template #footer="{ close }">
      <UButton
        color="neutral"
        variant="outline"
        :label="t('workflowFiles.cancel')"
        @click="close"
      />
      <UButton
        color="primary"
        :label="overwrite ? t('workflowFiles.overwrite') : t('workflowFiles.save')"
        :loading="saving"
        :disabled="!!nameError"
        @click="confirmSave"
      />
    </template>
  </UModal>

  <UModal
    v-model:open="browseOpen"
    :title="t('workflowFiles.chooseFolderTitle')"
    :description="t('workflowFiles.chooseFolderDescription')"
  >
    <template #body>
      <WorkflowFileBrowser v-model:dir="browseDir" mode="directories" />
    </template>
    <template #footer="{ close }">
      <UButton
        color="neutral"
        variant="outline"
        :label="t('workflowFiles.cancel')"
        @click="close"
      />
      <UButton
        color="primary"
        :label="t('workflowFiles.selectFolder')"
        @click="chooseFolder"
      />
    </template>
  </UModal>
</template>
