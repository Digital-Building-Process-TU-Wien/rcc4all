import { spawn } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import process from 'node:process'

const TIMESTAMP_SEPARATOR_RE = /[:.]/g

export default defineEventHandler(async (event) => {
  const body = await readBody(event)

  if (!body) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Workflow JSON is required',
    })
  }

  const timestamp = new Date().toISOString().replace(TIMESTAMP_SEPARATOR_RE, '-').slice(0, -5)
  const filename = `workflow-${timestamp}.json`
  const resultsFilename = `results-${timestamp}.json`
  const devFilesDir = join(process.cwd(), '.dev-files')
  const workflowPath = join(devFilesDir, filename)
  const resultsPath = join(devFilesDir, resultsFilename)

  await mkdir(devFilesDir, { recursive: true })
  await writeFile(workflowPath, JSON.stringify(body, null, 2), 'utf-8')

  const runnerDir = join(process.cwd(), '..', 'runner')
  const command = 'uv'
  const args = ['run', 'openbim-runner', 'run', workflowPath]

  const runner = spawn(command, args, {
    cwd: runnerDir,
  })

  const encoder = new TextEncoder()
  const stream = event.node.res

  stream.setHeader('Content-Type', 'text/event-stream; charset=utf-8')
  stream.setHeader('Cache-Control', 'no-cache')
  stream.setHeader('Connection', 'keep-alive')
  stream.setHeader('X-Accel-Buffering', 'no')

  const sendEvent = (type: string, data: any) => {
    const payload = `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`
    stream.write(encoder.encode(payload))
  }

  let stdoutData = ''
  let stderrData = ''

  runner.stdout.on('data', (data) => {
    const chunk = data.toString()
    stdoutData += chunk
    sendEvent('stdout', { chunk, timestamp: Date.now() })
  })

  runner.stderr.on('data', (data) => {
    const chunk = data.toString()
    stderrData += chunk
    sendEvent('stderr', { chunk, timestamp: Date.now() })
  })

  runner.on('error', (error) => {
    sendEvent('error', {
      message: 'Failed to start runner process',
      error: error.message,
      code: error.name,
    })
  })

  runner.on('close', async (code) => {
    let results: any
    let parseError: string | null = null

    if (stdoutData.trim()) {
      try {
        results = JSON.parse(stdoutData)
      }
      catch (e: any) {
        parseError = e.message
        results = { raw: stdoutData }
      }
    }

    const success = code === 0 && !parseError

    const resultPayload = {
      success,
      results,
      stderr: stderrData || undefined,
      parseError,
      exitCode: code,
    }

    await writeFile(resultsPath, JSON.stringify(resultPayload, null, 2), 'utf-8')

    sendEvent('complete', {
      success,
      resultsPath: resultsFilename,
      workflowPath: filename,
      results,
      stderr: stderrData || undefined,
      parseError,
      exitCode: code,
    })

    stream.end()
  })

  sendEvent('started', {
    workflowPath: filename,
    message: 'Runner process started',
  })
})
