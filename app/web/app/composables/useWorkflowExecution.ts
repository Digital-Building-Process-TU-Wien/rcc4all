import type { Ref } from 'vue'

const LINE_BREAK_RE = /\r?\n/
const EVENT_SEPARATOR_RE = /\r?\n\r?\n/

export interface StreamOutput {
  chunk: string
  timestamp: number
  type: 'stdout' | 'stderr'
}

export interface ExecutionError {
  message: string
  code?: string | number
  stderr?: string
}

export interface CompleteResult {
  success: boolean
  resultsPath: string
  workflowPath: string
  results?: any
  stderr?: string
  parseError?: string | null
  exitCode?: number | null
}

export interface WorkflowData {
  ifc_path: string
  nodes: Array<{
    id: string
    type: string
    label: string
    settings: any
    input_bindings: Record<string, string>
  }>
  edges: Array<{
    source: string
    target: string
  }>
}

interface ExecutionCallbacks {
  onStdout: (chunk: string, timestamp: number) => void
  onStderr: (chunk: string, timestamp: number) => void
  onError: (error: ExecutionError) => void
  onComplete: (result: CompleteResult) => void
}

export function useWorkflowExecution(workflow: Ref<WorkflowData | null>) {
  const isRunning = ref(false)
  const outputLogs = ref<StreamOutput[]>([])
  const error = ref<ExecutionError | null>(null)
  const results = ref<any>(null)
  const parseError = ref<string | null | undefined>(null)
  const exitCode = ref<number | null | undefined>(null)
  const status = ref<'idle' | 'running' | 'complete' | 'error'>('idle')

  const outputContainerRef = ref<HTMLElement | null>(null)

  function scrollToBottom(el: HTMLElement | null) {
    if (!el)
      return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50
    if (atBottom) {
      nextTick(() => {
        el.scrollTop = el.scrollHeight
      })
    }
  }

  function parseEvent(eventText: string): { eventType: string, data: string } | null {
    const lines = eventText.split(LINE_BREAK_RE)
    let eventType = 'message'
    const dataLines: string[] = []

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim()
      }
      else if (line.startsWith('data: ')) {
        dataLines.push(line.slice(6))
      }
    }

    if (dataLines.length === 0)
      return null

    return {
      eventType,
      data: dataLines.join('\n'),
    }
  }

  async function startExecution(callbacks: ExecutionCallbacks) {
    if (!workflow.value) {
      throw new Error('No workflow data provided')
    }

    status.value = 'running'
    isRunning.value = true
    outputLogs.value = []
    error.value = null
    results.value = null
    parseError.value = null
    exitCode.value = null

    const abortController = new AbortController()

    try {
      const response = await fetch('/api/workflow/execute.sse', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(workflow.value),
        signal: abortController.signal,
      })

      if (!response.ok) {
        throw new Error('Failed to start execution')
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('Readable stream not supported')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done)
            break

          buffer += decoder.decode(value, { stream: true })
          const events = buffer.split(EVENT_SEPARATOR_RE)
          buffer = events.pop() || ''

          for (const eventText of events) {
            if (!eventText.trim())
              continue

            try {
              const parsed = parseEvent(eventText)
              if (!parsed)
                continue

              const { eventType, data } = parsed
              const eventData = JSON.parse(data)

              if (eventType === 'stdout') {
                outputLogs.value.push({
                  chunk: eventData.chunk,
                  timestamp: eventData.timestamp,
                  type: 'stdout',
                } as StreamOutput)
                callbacks.onStdout(eventData.chunk, eventData.timestamp)
                scrollToBottom(outputContainerRef.value)
              }
              else if (eventType === 'stderr') {
                outputLogs.value.push({
                  chunk: eventData.chunk,
                  timestamp: eventData.timestamp,
                  type: 'stderr',
                } as StreamOutput)
                callbacks.onStderr(eventData.chunk, eventData.timestamp)
                scrollToBottom(outputContainerRef.value)
              }
              else if (eventType === 'error') {
                error.value = eventData as ExecutionError
                status.value = 'error'
                callbacks.onError(eventData)
              }
              else if (eventType === 'complete') {
                const completeData = eventData as CompleteResult
                status.value = 'complete'
                isRunning.value = false
                results.value = completeData.results
                parseError.value = completeData.parseError
                exitCode.value = completeData.exitCode

                if (!completeData.success && completeData.stderr) {
                  error.value = { message: 'Execution failed', stderr: completeData.stderr }
                }

                callbacks.onComplete(completeData)
                await reader.cancel()
                return
              }
            }
            catch (parseErr: any) {
              console.warn('Failed to parse SSE event:', parseErr)
              continue
            }
          }
        }
      }
      finally {
        decoder.decode()
        reader.releaseLock()
      }
    }
    catch (e: any) {
      if (e.name === 'AbortError') {
        return
      }
      status.value = 'error'
      isRunning.value = false
      error.value = { message: e.message || 'Failed to execute workflow' }
      throw e
    }
  }

  function stopExecution() {
    abortAll()
  }

  function abortAll() {
    // Note: AbortController is created per execution, so we don't need to track it here
  }

  function reset() {
    status.value = 'idle'
    isRunning.value = false
    outputLogs.value = []
    error.value = null
    results.value = null
    parseError.value = null
    exitCode.value = null
  }

  return {
    isRunning,
    outputLogs,
    error,
    results,
    parseError,
    exitCode,
    status,
    outputContainerRef,
    startExecution,
    stopExecution,
    reset,
  }
}
